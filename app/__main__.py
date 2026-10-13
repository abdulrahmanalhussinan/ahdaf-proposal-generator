import uvicorn

from app import config

if __name__ == "__main__":
    print(f"\n  Ahdaf Proposal Generator  ->  http://{config.HOST}:{config.PORT}\n")
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, log_level="warning")
