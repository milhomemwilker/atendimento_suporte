"""Teste real da integração Groq, sem depender dos serviços Google."""
from pathlib import Path
import json
import re
import urllib.error

from dotenv import load_dotenv

from adapters import GroqInference


def main():
    load_dotenv(Path(__file__).with_name('.env'), override=False)
    try:
        model = GroqInference()
        print('Testando conexão com a Groq (openai/gpt-oss-20b)...')
        result = model.infer(
            'Responda somente com um objeto JSON: {"status":"ok"}.',
            'Teste de conexão. Retorne o JSON solicitado.',
        )
        if result != {'status': 'ok'}:
            print('A API respondeu, mas o conteúdo não corresponde ao teste esperado.')
            return 1
    except urllib.error.HTTPError as error:
        messages = {
            401: 'Chave inválida. Confira GROQ_API_KEY no .env.',
            403: 'Acesso negado. Confira as permissões da conta e do modelo.',
            429: 'Limite de uso atingido. Confira a quota da conta Groq.',
        }
        print(messages.get(error.code, f'Falha na API Groq (HTTP {error.code}).'))
        body = error.read(16384).decode('utf-8', errors='replace')
        try:
            detail = json.loads(body).get('error', {})
            if isinstance(detail, dict):
                detail = ' | '.join(str(detail.get(k, '')) for k in ('code', 'type', 'message'))
            else:
                detail = str(detail)
        except ValueError:
            detail = re.sub('<[^>]+>', ' ', body)
        detail = detail.replace(model.api_key, '[CHAVE OCULTA]')
        detail = re.sub(r'gsk_[A-Za-z0-9_-]+', '[CHAVE OCULTA]', detail)
        detail = ' '.join(detail.split())[:1200]
        if detail:
            print('Detalhe da recusa:', detail)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError):
        print('Não foi possível conectar à Groq. Confira a rede e tente novamente.')
        return 1
    except (ValueError, KeyError, IndexError, TypeError):
        print('Chave ausente ou resposta inválida. Confira GROQ_API_KEY no .env.')
        return 1
    print('Conexão e resposta validadas com sucesso. A chave não foi exibida.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
