# Indian Government Schemes Assistant

This application searches the included `rag_data/Indian_Schemes_RAG_Updated` artifacts. It preserves and uses the original `sentence-transformers/all-MiniLM-L6-v2` model configuration, 384-dimensional normalized embeddings, and FAISS `IndexFlatIP` index.

## Run on Windows PowerShell

The supplied archive is already extracted to `rag_data/Indian_Schemes_RAG_Updated`. Create the backend environment:

```powershell
cd F:\charan_pro\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example ..\.env
```

Edit `F:\charan_pro\.env` and set `GEMINI_API_KEY` to your Google AI Studio key. `GEMINI_MODEL` defaults to `gemini-2.5-flash` and can be changed there.

Start the API in the backend terminal:

```powershell
uvicorn app.main:app --reload --port 8000
```

Start the web app in a second terminal:

```powershell
cd F:\charan_pro\frontend
npm install
npm run dev
```

Open the URL Vite prints, usually `http://localhost:5173`.

## Checks and troubleshooting

Check backend readiness at `http://localhost:8000/api/health`. If it reports unavailable, verify all three required artifacts (`config.json`, `schemes.faiss`, `chunks.pkl`) remain under `rag_data/Indian_Schemes_RAG_Updated`. If the API reports Gemini unavailable, confirm the key and supported model in `.env`. The API accepts only the local Vite origin by default; change `FRONTEND_ORIGIN` if you use another local port.
