"""Quick test: upload progress report to local server."""
import io
import subprocess
import time

import pandas as pd
import requests

proc = subprocess.Popen(
    ['.venv/bin/python', '-m', 'uvicorn', 'app.main:app', '--port', '8004'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(4)

try:
    r = requests.post('http://localhost:8004/api/auth/login',
                       json={'email': 'admin@example.com', 'password': 'admin1234'})
    print('Login:', r.status_code)
    token = r.json()['access_token']

    df = pd.DataFrame({
        'ID': ['20210001', '20210001', '20210002'],
        'NAME': ['John Doe', 'John Doe', 'Jane Smith'],
        'Course': ['PBHL201', 'PBHL301', 'PBHL201'],
        'Grade': ['A', 'B+', 'A-'],
        'Year': ['2023', '2023', '2023'],
        'Semester': ['Fall', 'Fall', 'Fall'],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name='Progress Report')

    buf.seek(0)
    r = requests.post('http://localhost:8004/api/progress/PBHL/upload/progress-report',
                       headers={'Authorization': f'Bearer {token}'},
                       files={'file': ('test.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    print('Upload PBHL:', r.status_code, r.text[:300])

    buf.seek(0)
    r = requests.post('http://localhost:8004/api/progress/CSC/upload/progress-report',
                       headers={'Authorization': f'Bearer {token}'},
                       files={'file': ('test.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    print('Upload CSC:', r.status_code, r.text[:300])
finally:
    proc.terminate()
    proc.wait()
