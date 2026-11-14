import unittest
from unittest.mock import Mock
from web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.support = Mock()
        self.support.triage.return_value = {'acao': 'orientar', 'resposta': 'Confira a conexão.', 'fontes': []}
        self.support.open_ticket.return_value = {'registrado': True, 'protocolo': 'TI-teste'}
        self.app = create_app(support_factory=lambda: self.support)
        self.client = self.app.test_client()
        self.client.get('/')
        import re
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', self.client.get('/').text)[1]

    def post(self, **data):
        return self.client.post('/', data={'csrf': self.csrf, **data}, follow_redirects=True)

    def start(self):
        return self.post(action='triage', name='Ana', department='RH', question='Wifi falhou')

    def test_resolved_without_ticket(self):
        self.assertIn('Vamos tentar resolver?', self.start().text)
        self.assertIn('Nenhum chamado foi aberto.', self.post(action='resolved').text)
        self.support.open_ticket.assert_not_called()

    def test_open_once(self):
        self.start()
        self.post(action='escalate')
        self.assertIn('Selecione quem', self.post(action='open', impact='invalid').text)
        self.assertIn('TI-teste', self.post(action='open', impact='setor').text)
        self.post(action='open', impact='setor')
        self.support.open_ticket.assert_called_once_with('Ana', 'RH', 'Wifi falhou', 'Confira a conexão.', 'setor')

    def test_csrf_and_validation(self):
        self.assertEqual(self.client.post('/', data={'action': 'triage'}).status_code, 400)
        self.assertIn('Preencha nome', self.post(action='triage').text)
        self.support.triage.assert_not_called()

    def test_human_and_unconfirmed(self):
        self.support.open_ticket.return_value = {'registrado': False, 'mensagem': 'Consulte a planilha antes de repetir.', 'referencia_tentativa': 'TI-incerto'}
        self.post(action='triage', name='Ana', department='RH', question='<script>erro</script>', human='yes')
        self.support.triage.assert_not_called()
        response = self.post(action='open', impact='individual')
        self.assertIn('Gravação não confirmada', response.text)
        self.assertIn('TI-incerto', response.text)
        self.post(action='open', impact='individual')
        self.support.open_ticket.assert_called_once()
