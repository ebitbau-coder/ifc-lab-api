from fastapi import FastAPI, UploadFile, File
import tempfile
import ifcopenshell

app = FastAPI()

@app.get("/")
def root():
    return {"status": "IFC LAB RUNNING"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
        tmp.write(await file.read())
        path = tmp.name

    model = ifcopenshell.open(path)

    counts = {}
    for el in model.by_type("IfcProduct"):
        t = el.is_a()
        counts[t] = counts.get(t, 0) + 1

    return {"elements_total": sum(counts.values()), "types": counts}
