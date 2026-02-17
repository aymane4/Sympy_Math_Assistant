#!/bin/bash
# my fancy wait
wait_dots() {
  local i=0
  local max=$1
  while [[ $i -lt $max ]]; do
    echo -n "." # -n keeps it on the same line
    sleep 0.5
    ((i++)) # Correct way to do math in Bash
  done
  echo "" # Move to a new line when done
}
# sber nshuf wsh dik fichier exist wla la
# securité ou kda.
if [ ! -f requirements.txt ]; then
  echo "the requirements.txt does not exist"
  exit 1
fi

# installing the dependencies
# wa coode tbarkallah a khoya aymane 3ndk f main.py.
echo "Installing dependencies"
wait_dots 3
# had l command possi
pip install -r requirements.txt

if [ $? -eq 0 ]; then
  echo "everything is installed :D\n"
else
  echo "Something went Wrong"
  wait_dots 3
  exit 1
fi

# Gemini key
read -s -p "Input you're gemini key here: " $api_key

if [ -f .env ]; then
  if grep -q "GEMINI_API_KEY" .env; then
    echo "GEMINI_API_KEY already exists, rewriting the api key"
    wait_dots 3
    # yalah 3reft had l command, mferbla hhhh
    sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$api_key/" .env
  fi
else
  echo ".env does not exist, Creation Setup"
  wait_dots 3
  echo "GEMINI_API_KEY=$api_key" >.env
  echo "Done! .env has been created"

fi
