.PHONY: dev test lint demo clean

dev:
	pip3 install -e ".[dev]"

test:
	python3 -m pytest tests/ -q

lint:
	python3 -m ruff check .
	python3 -m ruff format --check .

demo:
	@echo "Submitting sample cases..."
	@for case in \
		'{"case_id":"CASE-2026-001","issue_type":"contestacao_cobranca","product_line":"cartao_credito","customer_tier":"standard","description":"Cobrança duplicada de R$$180","risk_flags":[],"documents":["fatura.pdf"],"valor_brl":180.0}' \
		'{"case_id":"CASE-2026-002","issue_type":"contestacao_cobranca","product_line":"cartao_credito","customer_tier":"personalite","description":"Contestação de R$$2300 em estabelecimento desconhecido","risk_flags":["fraude_suspeita"],"documents":["extrato.pdf","bo.pdf"],"valor_brl":2300.0}' \
		'{"case_id":"CASE-2026-003","issue_type":"contestacao_cobranca","product_line":"conta_corrente","customer_tier":"standard","description":"Tarifa cobrada em conta isenta","risk_flags":[],"documents":[],"valor_brl":32.90}' \
		'{"case_id":"CASE-2026-006","issue_type":"aumento_limite","product_line":"emprestimo","customer_tier":"standard","description":"Ampliação de crédito com parcelas em atraso","risk_flags":["inadimplencia_ativa"],"documents":[],"valor_brl":8000.0}' \
	; do \
		echo "\n--- Submitting case ---"; \
		curl -s -X POST http://localhost:8000/cases/submit \
			-H "Content-Type: application/json" \
			-d "$$case" | python3 -m json.tool; \
	done
	@echo "\n--- All cases ---"
	@curl -s http://localhost:8000/cases | python3 -m json.tool

clean:
	rm -rf dist/ build/ src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
