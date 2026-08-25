lancer en local depuis la racine
conda env create -f environment.yml
conda activate lightfm_env
cd ingestion/
pytest tests/test_ingestion.py -v