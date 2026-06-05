module.exports = {
  apps: [
    {
      name: "uidb-backend",
      script: ".venv\\Scripts\\python.exe",
      args: "-m uvicorn app.main:app --host 0.0.0.0 --port 8000",
      cwd: "f:\\UIDB SEARCH PORTAL\\backend",
      interpreter: "none"
    },
    {
      name: "uidb-frontend",
      script: "npx.cmd",
      args: "serve -s dist -l 5173",
      cwd: "f:\\UIDB SEARCH PORTAL",
      interpreter: "none"
    }
  ]
};
