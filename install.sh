echo 'Installing Ubuntu Dependencies'
sudo apt-get update
sudo apt install -y python3-venv

echo 'Creating Virtual Environment'
python3 -m venv venv
source "venv/bin/activate"
pip install -r requirements.txt