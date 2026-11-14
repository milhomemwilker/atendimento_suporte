"""Executa cenários completos no terminal, com chamados somente locais."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    tickets = root / 'chamados_demo.jsonl'
    scenarios = [
        ('Wi-Fi resolvido', ['Teste Ana', 'RH', 'Como configurar wifi?', 'n', 's'], None),
        ('Impressora sem resolução', ['Teste Bruno', 'Financeiro', 'Impressora falhando', 'n', 'n', 'individual'], 'Normal'),
        ('Servidor sem documentação', ['Teste Carla', 'Operações', 'Servidor indisponível', 'n', 'setor'], 'Alta'),
        ('Atendimento humano', ['Teste Diego', 'TI', 'Sistema indisponível para todos', 's', 'empresa'], 'Crítica'),
        ('Incidente de segurança', ['Teste Eva', 'TI', 'Suspeita de invasão', 's', 'seguranca'], 'Crítica'),
    ]
    report = []
    for name, inputs, priority in scenarios:
        before = tickets.read_bytes() if tickets.exists() else b''
        run = subprocess.run(
            [sys.executable, str(root / 'app.py'), '--demo'],
            input='\n'.join(inputs) + '\n', capture_output=True,
            text=True, encoding='utf-8', cwd=root,
            env={**os.environ, 'PYTHONUTF8': '1'}, timeout=30,
        )
        assert run.returncode == 0, f'{name}: execução falhou'
        after = tickets.read_bytes() if tickets.exists() else b''
        assert after.startswith(before), f'{name}: histórico foi alterado'
        rows = [json.loads(line) for line in after[len(before):].decode('utf-8').splitlines()]
        if priority is None:
            assert not rows and 'encerrado como resolvido' in run.stdout, name
            result = {'cenario': name, 'resultado': 'Resolvido sem chamado'}
        else:
            assert len(rows) == 1, f'{name}: quantidade de chamados incorreta'
            row = rows[0]
            assert len(row) == 9 and row[-2:] == [priority, 'Aberto'], name
            assert row[0] in run.stdout and '"registrado": true' in run.stdout, name
            result = {'cenario': name, 'resultado': 'Chamado local aberto', 'prioridade': priority, 'protocolo': row[0]}
        report.append(result)
        print(f'OK: {name} — {result["resultado"]}')
    (root / 'RELATORIO_SIMULACOES.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    print('5 cenários aprovados. Relatório: RELATORIO_SIMULACOES.json')


if __name__ == '__main__':
    main()
