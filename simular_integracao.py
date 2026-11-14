"""Simulações reais: lê Docs, consulta Groq e grava testes no Sheets."""
import json
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
from adapters import GoogleDocs, GoogleSheets, GroqInference, google_services
from core import Support


def main():
    root = Path(__file__).resolve().parent
    load_dotenv(root / '.env', override=False)
    report_path = root / 'RELATORIO_INTEGRACAO.json'
    report = {'execucao': uuid4().hex[:10], 'inicio': datetime.now().astimezone().isoformat(), 'cenarios': []}
    try:
        docs_api, sheets_api = google_services(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
        ids = [s.strip() for s in os.environ['GOOGLE_DOC_IDS'].split(',') if s.strip()]
        if not ids:
            raise ValueError('Documentos não configurados')
        docs = GoogleDocs(docs_api, ids)
        chunks = docs.read()
        if not any(c.text.strip() for c in chunks):
            raise ValueError('Base sem texto')
        report['trechos_disponiveis'] = len(chunks)
        tickets = GoogleSheets(sheets_api, os.environ['GOOGLE_SHEET_ID'], os.getenv('GOOGLE_SHEET_TAB', 'Chamados'))
        tickets.init()
        support = Support(docs, GroqInference(), tickets)
        # A pergunta derivada da base permite testar recuperação com conteúdo disponível.
        first = next(c for c in chunks if c.text.strip())
        question = 'Como proceder neste caso documentado? ' + first.text[:600]
        scenarios = [
            ('Orientação com base disponível', question, None, False),
            ('Orientação não resolveu', question, 'individual', False),
            ('Servidor indisponível', 'Servidor indisponível para o setor. Como proceder?', 'setor', False),
            ('Humano solicitado', 'Sistema indisponível para toda a empresa.', 'empresa', True),
            ('Incidente de segurança', 'Suspeita de invasão. Solicito atendimento humano.', 'seguranca', True),
        ]
        for name, question, impact, human in scenarios:
            result = {'acao': 'encaminhar', 'resposta': 'Atendimento humano solicitado.', 'fontes': []} if human else support.triage(question)
            entry = {'cenario': name, 'acao': result['acao'], 'fontes': len(result['fontes'])}
            report['cenarios'].append(entry)
            if impact is None:
                entry['resultado'] = 'Resolução simulada sem chamado' if result['acao'] == 'orientar' else 'Não houve orientação validada; resolução não simulada'
            else:
                entry.update(support.open_ticket(
                    '[TESTE AUTOMATIZADO] ' + report['execucao'], 'TESTES - DESCONSIDERAR',
                    '[SIMULAÇÃO SEM INCIDENTE REAL] ' + name + ': ' + question,
                    result['resposta'], impact,
                ))
                entry['impacto'] = impact
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(name + ': ' + str(entry.get('protocolo') or entry.get('resultado') or entry.get('mensagem')), flush=True)
        rows = sheets_api.spreadsheets().values().get(spreadsheetId=tickets.id, range=tickets.range).execute().get('values', [])
        for entry in report['cenarios']:
            if entry.get('protocolo'):
                matches = [r for r in rows if r and r[0] == entry['protocolo']]
                entry['linhas_confirmadas'] = len(matches)
                entry['prioridade'] = matches[0][7] if matches and len(matches[0]) > 7 else None
                entry['status'] = matches[0][8] if matches and len(matches[0]) > 8 else None
        report['concluido'] = True
    except Exception as error:
        report['concluido'] = False
        report['erro_tipo'] = type(error).__name__
        report['http_status'] = getattr(getattr(error, 'resp', None), 'status', None)
        print('Integração interrompida: ' + type(error).__name__ + '. Consulte o relatório. Não repita gravações sem conferir a planilha.', flush=True)
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report.get('concluido') else 1


if __name__ == '__main__':
    raise SystemExit(main())
