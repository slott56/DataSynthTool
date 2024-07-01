.PHONY : tests hints demo

tests :
	tox

demo :
	PYTHONPATH=src python tests/sample_app.py

notebooks/data_model.png : notebooks/data_model.puml
	plantuml notebooks/data_model.puml

docs/synthetic_data.slides.html : notebooks/synthetic_data.ipynb notebooks/data_model.png
	jupyter nbconvert notebooks/synthetic_data.ipynb --to slides --output-dir=docs
