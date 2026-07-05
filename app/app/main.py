import uvicorn
import gradio as gr
from fastapi import FastAPI

from app.api import router
from app.config import GRADIO_PORT
from app.ui import build_ui


app = FastAPI(title="TalkAgent")
app.include_router(router)

ui = build_ui()
app = gr.mount_gradio_app(app, ui, path="/")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=GRADIO_PORT)
