"""Adaptadores Google Workspace e Groq; dependências carregadas sob demanda."""
import json
import urllib.request
from core import Chunk

SCOPES = ['https://www.googleapis.com/auth/documents.readonly', 'https://www.googleapis.com/auth/spreadsheets']
HEADERS = ['Protocolo','Data/hora','Colaborador','Setor','Descrição','Orientações realizadas','Impacto','Prioridade','Status']

def extract_text(content):
    pieces = []
    for item in content:
        for element in item.get('paragraph',{}).get('elements',[]):
            pieces.append(element.get('textRun',{}).get('content',''))
        for row in item.get('table',{}).get('tableRows',[]):
            for cell in row.get('tableCells',[]):
                pieces.append(extract_text(cell.get('content',[])))
        if 'tableOfContents' in item:
            pieces.append(extract_text(item['tableOfContents'].get('content',[])))
    return ''.join(pieces)

def tab_contents(tabs):
    for tab in tabs:
        yield tab.get('documentTab',{}).get('body',{}).get('content',[])
        yield from tab_contents(tab.get('childTabs',[]))

class GoogleDocs:
    def __init__(self, service, ids):
        self.service, self.ids = service, ids
    def read(self):
        chunks = []
        for doc_id in self.ids:
            doc = self.service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
            bodies = list(tab_contents(doc.get('tabs',[]))) if doc.get('tabs') else [doc.get('body',{}).get('content',[])]
            for tab_index, body in enumerate(bodies):
                text = extract_text(body)
                for offset in range(0,len(text),1400):
                    chunks.append(Chunk(f'{doc_id}:{tab_index}:{offset}',doc.get('title',doc_id),text[offset:offset+1800],f'https://docs.google.com/document/d/{doc_id}/edit'))
        return chunks

class GoogleSheets:
    def __init__(self, service, spreadsheet_id, sheet='Chamados'):
        self.service, self.id = service, spreadsheet_id
        self.range = "'"+sheet.replace("'","''")+"'!A:I"
    def append(self, row):
        result = self.service.spreadsheets().values().append(spreadsheetId=self.id,range=self.range,valueInputOption='RAW',insertDataOption='INSERT_ROWS',body={'values':[row]}).execute(num_retries=0)
        if result.get('updates',{}).get('updatedRows') != 1:
            raise RuntimeError('Quantidade de linhas não confirmada')
    def init(self):
        values = self.service.spreadsheets().values()
        existing = values.get(spreadsheetId=self.id,range=self.range.replace('!A:I', '!A1:I1')).execute().get('values',[])
        if existing:
            if existing[0] != HEADERS:
                raise ValueError('Cabeçalho incompatível; use uma aba vazia.')
            return
        values.update(spreadsheetId=self.id,range=self.range,valueInputOption='RAW',body={'values':[HEADERS]}).execute()

class GroqInference:
    """GPT-OSS-20B hospedado na Groq. Chave somente por ambiente."""
    def __init__(self):
        import os
        self.api_key = os.environ.get('GROQ_API_KEY', '').strip()
        if not self.api_key:
            raise ValueError('Configure GROQ_API_KEY no ambiente.')

    def infer(self, system, user):
        # Endpoint fixo: impede enviar a chave para um host configurado por engano.
        payload = {
            'model': 'openai/gpt-oss-20b',
            'stream': False,
            'temperature': 0,
            'max_completion_tokens': 4096,
            'reasoning_effort': 'low',
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
        }
        request = urllib.request.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json',
                     'User-Agent': 'atendimento-gpt/1.0',
                     'Authorization': 'Bearer ' + self.api_key},
            method='POST',
        )
        # Não segue redirects com credenciais; erros são tratados pela triagem.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=90) as response:
            result = json.load(response)
        choice = result['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Resposta interrompida ou incompleta.')
        return json.loads(choice['message']['content'])


def google_services(credentials_file):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    credentials = service_account.Credentials.from_service_account_file(credentials_file,scopes=SCOPES)
    return build('docs','v1',credentials=credentials), build('sheets','v4',credentials=credentials)
