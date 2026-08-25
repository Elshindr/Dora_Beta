lancer en local depuis la racine
conda env create -f environment.yml
conda activate lightfm_env
cd back/
pytest tests/test_api.py -v