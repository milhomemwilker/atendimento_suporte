"""Interface local de suporte. Execute: python web.py [--demo]."""
import argparse
import os
import secrets
from pathlib import Path
from threading import RLock

from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for

from adapters import GoogleDocs, GoogleSheets, GroqInference, google_services
from app import DemoDocs, DemoModel, DemoTickets
from core import Support


def create_app(demo=False, support_factory=None):
    load_dotenv(Path(__file__).with_name('.env'), override=False)
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config.update(MAX_CONTENT_LENGTH=20000, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
    states = {}
    lock = RLock()

    def support():
        if support_factory:
            return support_factory()
        if demo:
            return Support(DemoDocs(), DemoModel(), DemoTickets())
        required = ['GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_DOC_IDS', 'GOOGLE_SHEET_ID', 'GROQ_API_KEY']
        if any(not os.getenv(k, '').strip() for k in required):
            raise ValueError('Configuração incompleta')
        docs, sheets = google_services(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
        ids = [s.strip() for s in os.environ['GOOGLE_DOC_IDS'].split(',') if s.strip()]
        if not ids:
            raise ValueError('Documentos ausentes')
        return Support(GoogleDocs(docs, ids), GroqInference(), GoogleSheets(sheets, os.environ['GOOGLE_SHEET_ID'], os.getenv('GOOGLE_SHEET_TAB', 'Chamados')))

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.route('/', methods=['GET', 'POST'])
    def index():
        if 'sid' not in session:
            session['sid'] = secrets.token_urlsafe(24)
        sid = session['sid']
        with lock:
            state = states.setdefault(sid, {'csrf': secrets.token_urlsafe(24), 'stage': 'form'})
            error = None
            if request.method == 'POST':
                if not secrets.compare_digest(request.form.get('csrf', ''), state['csrf']):
                    abort(400)
                action = request.form.get('action')
                if action == 'new':
                    states[sid] = {'csrf': secrets.token_urlsafe(24), 'stage': 'form'}
                    return redirect(url_for('index'))
                if action == 'triage' and state['stage'] == 'form':
                    data = {k: request.form.get(k, '').strip() for k in ('name', 'department', 'question')}
                    state['data'] = data
                    if not all(data.values()) or len(data['name']) > 200 or len(data['department']) > 200 or len(data['question']) > 4000:
                        error = 'Preencha nome, setor e problema respeitando os limites indicados.'
                    else:
                        try:
                            state['human'] = request.form.get('human') == 'yes'
                            state['result'] = {'acao': 'encaminhar', 'resposta': 'Você solicitou atendimento humano. Informe o impacto para registrar o chamado.', 'fontes': []} if state['human'] else support().triage(data['question'])
                            state['stage'] = 'guidance' if state['result']['acao'] == 'orientar' else 'ticket'
                            return redirect(url_for('index'))
                        except Exception:
                            error = 'Não foi possível iniciar o atendimento. Confira as configurações do Google e da Groq no servidor.'
                elif action == 'resolved' and state['stage'] == 'guidance':
                    state['stage'] = 'resolved'
                    return redirect(url_for('index'))
                elif action == 'escalate' and state['stage'] == 'guidance':
                    state['stage'] = 'ticket'
                    return redirect(url_for('index'))
                elif action == 'open' and state['stage'] == 'ticket':
                    impact = request.form.get('impact', '')
                    if impact not in ('individual', 'setor', 'empresa', 'seguranca'):
                        error = 'Selecione quem está sendo afetado.'
                    else:
                        try:
                            service = support()
                        except Exception:
                            error = 'Não foi possível conectar ao serviço. Confira as configurações no servidor.'
                        else:
                            # Trava e estado impedem repetir o envio por atualização ou clique duplo.
                            state['stage'] = 'done'
                            data = state['data']
                            state['ticket'] = service.open_ticket(data['name'], data['department'], data['question'], '' if state['human'] else state['result']['resposta'], impact)
                            return redirect(url_for('index'))
            return render_template('index.html', state=state, error=error, demo=demo)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    create_app(args.demo).run(host='127.0.0.1', port=args.port, debug=False)
