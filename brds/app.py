from os.path import isfile
from typing import Any, Dict

import pandas as pd
from fastapi import FastAPI, HTTPException, Path, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from brds import fload, get_dataset_files, get_safe_path, list_datasets

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:8080",
    "https://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


templates = Jinja2Templates(directory="./brds/templates")


@app.get("/dictionary/{filename:path}")
async def read_as_dict(filename: str = Path(..., regex=r"[\w\-/]+")) -> Dict[str, Any]:
    try:
        df = fload(str(get_safe_path(filename)))
        return df.to_dict(orient="records")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Parquet file '{filename}' not found") from exc


@app.get("/raw/{filename:path}")
async def read_raw(filename: str = Path(..., regex=r"[\w\-/]+")) -> Any:
    try:
        df = fload(str(get_safe_path(filename)))
        if isinstance(df, pd.DataFrame):
            return df.to_dict(orient="records")
        return df
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Parquet file '{filename}' not found") from exc


@app.get("/html/{filename:path}", response_class=HTMLResponse)
async def read_html(filename: str = Path(..., regex=r"[\w\-/]+")) -> str:
    try:
        df: pd.DataFrame = fload(str(get_safe_path(filename)))
        return df.to_html()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Parquet file '{filename}' not found") from exc


@app.get("/datasets", response_class=HTMLResponse)
async def get_datasets(request: Request) -> Response:
    datasets = list_datasets()
    return templates.TemplateResponse("datasets.html", {"request": request, "modules": datasets})


@app.get("/download/{path:path}", response_class=FileResponse)
async def download_file(path: str):
    safe_path = get_safe_path(path)

    if not isfile(safe_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(safe_path, filename=path.split("/")[-1], media_type="application/octet-stream")


@app.get("/dataset/{dataset_name:path}", response_class=HTMLResponse)
async def dataset_files(request: Request, dataset_name: str):
    grouped_files = get_dataset_files(str(get_safe_path(dataset_name)))
    return templates.TemplateResponse(
        "dataset_files.html", {"request": request, "dataset_name": dataset_name, "grouped_files": grouped_files}
    )
