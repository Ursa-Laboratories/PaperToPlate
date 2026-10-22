import uvicorn
from .config import PORT

uvicorn.run("paper_to_plate.app:app", host="127.0.0.1", port=PORT)
