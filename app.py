"""Interface de terminal para demonstração e piloto supervisionado."""
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from core import Chunk, Support
from adapters import GoogleDocs, GoogleSheets, GroqInference, google_services

class ConfigurationError(ValueError):
    """Erro de configuração com mensagem segura para o terminal."""

class DemoDocs:
    def read(self):
        return [
            Chunk(**c)
            for c in json.loads(
                Path(__file__)
                .with_name('examples')
                .joinpath('base.json')
                .read_text(encoding='utf-8')
            )
        ]
class DemoModel:
    def infer(self, system, user):
        data = json.loads(user)
        c = data['trechos'][0]
        return {'acao':'orientar','resposta':c['text'],'fontes':[c['id']]}
class DemoTickets:
    def append(self,row):
        with Path('chamados_demo.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')

def main():
    load_dotenv(Path(__file__).with_name('.env'), override=False)
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--init-sheet',action='store_true')
    args = parser.parse_args()
    if args.demo:
        support = Support(DemoDocs(),DemoModel(),DemoTickets())
        print('DEMO: respostas simuladas; gravação local em chamados_demo.jsonl.')
    else:
        required = ['GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_SHEET_ID']
        if not args.init_sheet:
            required.extend(['GOOGLE_DOC_IDS', 'GROQ_API_KEY'])
        missing = [name for name in required if not os.getenv(name, '').strip()]
        if missing:
            raise ConfigurationError('Preencha no .env: ' + ', '.join(missing) + '.')
        if not Path(os.environ['GOOGLE_APPLICATION_CREDENTIALS']).is_file():
            raise ConfigurationError('Arquivo de credenciais Google não encontrado. Confira GOOGLE_APPLICATION_CREDENTIALS no .env.')
        ids = [s.strip() for s in os.getenv('GOOGLE_DOC_IDS', '').split(',') if s.strip()]
        if not args.init_sheet and not ids:
            raise ConfigurationError('Preencha GOOGLE_DOC_IDS com os documentos autorizados.')
        model = None if args.init_sheet else GroqInference()
        docs, sheets = google_services(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
        tickets = GoogleSheets(sheets,os.environ['GOOGLE_SHEET_ID'],os.getenv('GOOGLE_SHEET_TAB','Chamados'))
        if args.init_sheet:
            tickets.init()
            print('Cabeçalho validado/criado.')
            return
        support = Support(GoogleDocs(docs,ids),model,tickets)
    name = input('Nome: ').strip()
    department = input('Setor: ').strip()
    question = input('Descreva o problema (não informe senhas): ').strip()
    human = input('Deseja atendimento humano diretamente? [s/N]: ').lower() == 's'
    result = {'acao':'encaminhar','resposta':'Atendimento humano solicitado.','fontes':[]} if human else support.triage(question)
    print(result['resposta'])
    for source in result['fontes']:
        print('Fonte:',source['titulo'],source['url'])
    if result['acao']=='orientar' and input('O problema foi resolvido? [s/N]: ').lower()=='s':
        print('Atendimento encerrado como resolvido pelo colaborador.')
        return
    impact = input('Impacto [individual/setor/empresa/seguranca]: ').strip()
    ticket = support.open_ticket(name,department,question,'' if human else result['resposta'],impact)
    print(json.dumps(ticket,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nAtendimento interrompido; cadastro não confirmado.')
    except ConfigurationError as error:
        print(error)
        raise SystemExit(1)
    except Exception:
        print('Falha de configuração ou entrada. Verifique variáveis, permissões e serviços. Cadastro não confirmado.')
        raise SystemExit(1)
