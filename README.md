# GunGong

<p align="center">
  <img src="src/frontend/public/img/mascot_01.png" width="80" alt="GunGong mascot with a clipboard">
  <img src="src/frontend/public/img/mascot_02.png" width="80" alt="GunGong mascot 2">
  <img src="src/frontend/public/img/mascot_03.png" width="80" alt="GunGong mascot 3">
  <img src="src/frontend/public/img/mascot_04.png" width="80" alt="GunGong mascot 4">
</p>

**GunGong (กันโกง) is a LINE MINI App that helps users assess suspicious links, QR codes, and messages before clicking or responding.** Users can check content, read risk explanations in Thai, revisit their scan history, share a result with friends, and exchange scam warnings through a community feed - all within LINE.

![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-087F73?style=for-the-badge&logo=fastapi&logoColor=white)
![Gemini 3.5 Flash-Lite](https://img.shields.io/badge/Gemini_3.5_Flash--Lite-FFFFFF?style=for-the-badge&logo=googlegemini&logoColor=6C7FF2)
![VirusTotal](https://img.shields.io/badge/VirusTotal-394EFF?style=for-the-badge&logo=virustotal&logoColor=white)
![Cloud Firestore](https://img.shields.io/badge/Cloud_Firestore-DD2C00?style=for-the-badge&logo=firebase&logoColor=white)

## What you can do

- **Check links and QR codes:** Paste a URL, scan a QR code with the camera, or choose a QR image. Review the decoded link before submitting it for URL checks, page analysis, and available threat-reputation evidence.
- **Analyze suspicious messages:** Submit text to identify scam intent, impersonation, and gambling promotion, with AI-generated explanations in Thai.
- **Revisit your history:** Browse and filter personal scan records, open result details, and review summary charts for up to 50 recent records on Home.
- **Share a result in LINE:** Preview a minimized result, choose friends or groups with Share Target Picker, and let recipients open that result's detail page without exposing your full history.
- **Exchange community warnings:** Create text/image posts, like and comment on posts, and edit or delete your own contributions.
- **Submit a tip:** Report a suspicious link or message, receive a reference number, and revisit its review status. An optional Service Message integration sends a thank-you confirmation after a tip is saved.
- **Use the chatbot companion:** Send suspicious text or a QR image to the LINE bot and receive analysis through the same backend services.

Automated results are indicators, not guarantees of safety. Missing evidence is shown as incomplete rather than proof that a link is safe.

## Tech stack

| Area | Tools | Role |
| --- | --- | --- |
| LINE integration | LINE MINI App, LIFF SDK, LINE Login, Messaging API | In-LINE experience, user identity, chatbot replies, Share Target Picker, and optional Service Messages |
| Frontend | React 19, Vite 7, JavaScript, Recharts | Mobile UI, scan forms, history, and summary charts |
| Backend | Python 3.12, FastAPI, Pydantic, HTTPX | API endpoints, validation, and provider integrations |
| AI analysis | [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), LangChain | Message-intent classification, page-content analysis, and Thai explanations |
| URL reputation | VirusTotal API | Available URL threat reports alongside local and AI checks |
| Database | Cloud Firestore | Scan history, cached results, community posts, tips, and shared-result snapshots |
| QR decoding | jsQR, zxing-cpp, Pillow | Local camera/image decoding without AI image uploads |
| Tests | Python unittest, Node.js test runner | Backend and frontend regression checks |

<details>
<summary>Local development and checks</summary>

Requires Python 3.12 and Node.js 22.12+ with npm. Create a private root `.env` using the [backend settings](src/backend/core/config.py). Typical keys are `GOOGLE_API_KEY`, `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`, `FIRESTORE_PROJECT_ID`, and `GOOGLE_APPLICATION_CREDENTIALS` (a local service-account file path).

The project configuration uses `GEMINI_MODEL=gemini-3.5-flash-lite`. Set it explicitly: the source-code fallback is still `gemini-2.5-flash-lite`. Hosted environments must be configured separately.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn src.backend.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd src/frontend
npm.cmd ci
npm.cmd run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

- Configure your own `VITE_LIFF_ID`, `VITE_LINE_ENDPOINT_URL`, and `LINE_LOGIN_CHANNEL_ID` in the root `.env`; enable `shareTargetPicker` in the matching LINE channel. LINE features need a reachable endpoint and real-device testing.
- Service Messages are disabled by default and require matching MINI App credentials and flags. Unverified apps are limited to Developing testers; Published use requires LINE verification and template approval.
- `VITE_FIREBASE_*` analytics settings are optional. Never put server secrets in `VITE_*`: these values are public in the browser build.

Run checks from the repository root:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests
npm.cmd --prefix src/frontend test
npm.cmd --prefix src/frontend run build
```

This repository contains source and local tooling, not a hosted demo or cloud deployment configuration.

</details>

<details>
<summary>Data and safety notes</summary>

- Personal history and tip details require owner authentication. Shared links expire after 7 days and can be forwarded by anyone holding the link. Preview before sharing; masking is not guaranteed anonymization, and revocation cannot erase sent cards or screenshots.
- A tip receipt confirms storage, not completed review.
- Use [deny-all client rules](config/firestore.production.rules) for Firestore, with server access controlled separately. `config/firestore.rules` is permissive and **for the emulator only**.
- URL rendering and unknown-URL submission to VirusTotal are off by default. Untrusted URL fetching needs network isolation; the [optional local renderer](scripts/local-url-renderer/README.md) is not a production security boundary.
- Keep `.env`, credentials, and user data out of Git. Deleting a secret does not erase Git history; revoke exposed keys before making a repository public.

</details>

[Backend](src/backend/) · [Frontend](src/frontend/README.md) · [Tests](tests/) · [Local tools](scripts/README.md) · [License](LICENSE)
