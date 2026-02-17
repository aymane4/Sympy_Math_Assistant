# image dyal code (ina language)
FROM python:3.12.0-slim

WORKDIR /mathapp

# ka tcopy f lwl requirements bash dependencies ykono 3ndk f image
COPY requirements.txt .

# installi dependcies
RUN pip install --no-cache-dir -r requirements.txt

# hadi ka tcopy ga3 l'app code
COPY . .

# runi l code dyalk
CMD [ "python" , "main.py" ]
