.PHONY: install test data eval eval-llm run
install:  ; python -m pip install -r requirements-dev.txt
test:     ; python -m pytest -q
data:     ; python evals/generate_dataset.py --split dev --n 60 && python evals/generate_dataset.py --split holdout --n 40
eval:     ; python evals/run_eval.py --extractor rules --split dev && python evals/run_eval.py --extractor rules --split holdout
eval-llm: ; python evals/run_eval.py --extractor llm --split dev && python evals/run_eval.py --extractor llm --split holdout
run:      ; uvicorn docflow.api:app --reload
