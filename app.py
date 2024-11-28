from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pymongo import MongoClient
import uvicorn

app = FastAPI()

# Initial MongoDB connection details
MONGO_DETAILS = "mongodb://localhost:27017"
client = MongoClient(MONGO_DETAILS)
db = client["ehr_database"]
patients_collection = db["patients"]

# Authentication constants
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "cse-512-master-password"

# Models for Patient and Medical Records
class Coding(BaseModel):
    system: str
    code: str
    display: str

class Condition(BaseModel):
    id: str
    code: Dict[str, List[Coding]]
    onsetDateTime: str
    clinicalStatus: str

class Medication(BaseModel):
    status: str
    stage: str
    medication: str
    patientReference: str
    contextReference: str
    dateWritten: str
    dosageInstruction: List[Dict[str, Optional[Any]]]

class Observation(BaseModel):
    id: str
    code: str
    value: Optional[str]
    unit: Optional[str]
    effectiveDateTime: str
    components: List[Any]

class MedicalRecords(BaseModel):
    conditions: List[Condition]
    medications: List[Medication]
    observations: List[Observation]

class Patient(BaseModel):
    patientID: str
    name: str
    age: int
    gender: str
    region: str
    medicalRecords: MedicalRecords

# Model for MongoDB connection updates
class ConnectionDetails(BaseModel):
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    database: str

# Middleware to validate admin credentials
def authenticate_admin(username: str = Header(None), password: str = Header(None)):
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

# API: Change MongoDB connection details
@app.post("/api/v1/admin/change-connection", dependencies=[Depends(authenticate_admin)])
def change_connection(details: ConnectionDetails):
    global client, db, patients_collection

    try:
        # Build new connection URI
        if details.username and details.password:
            mongo_uri = f"mongodb://{details.username}:{details.password}@{details.host}:{details.port}"
        else:
            mongo_uri = f"mongodb://{details.host}:{details.port}"

        # Close existing connection
        client.close()

        # Establish new connection
        client = MongoClient(mongo_uri)
        db = client[details.database]
        patients_collection = db["patients"]

        return {"message": "MongoDB connection updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update connection: {str(e)}")

# API: Create a new patient
@app.post("/api/v1/patients")
def create_patient(patient: Patient):
    patient_data = patient.dict()
    result = patients_collection.insert_one(patient_data)
    return {"message": "Patient record created successfully", "patient_id": str(result.inserted_id)}

# API: Get a patient by ID
@app.get("/api/v1/patients/{patient_id}")
def get_patient(patient_id: str):
    patient = patients_collection.find_one({"patientID": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

# API: Update a patient record
@app.put("/api/v1/patients/{patient_id}")
def update_patient(patient_id: str, update_data: Dict[str, Any]):
    update_result = patients_collection.update_one(
        {"patientID": patient_id},
        {"$set": update_data}
    )
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient record updated successfully"}

# API: Get medical records for a patient
@app.get("/api/v1/patients/{patient_id}/medical-records")
def get_medical_records(patient_id: str):
    patient = patients_collection.find_one({"patientID": patient_id}, {"_id": 0, "medicalRecords": 1})
    if not patient or "medicalRecords" not in patient:
        raise HTTPException(status_code=404, detail="Medical records not found")
    return patient["medicalRecords"]

# API: Update medical records for a patient
@app.put("/api/v1/patients/{patient_id}/medical-records")
def update_medical_records(patient_id: str, medical_records: MedicalRecords):
    update_result = patients_collection.update_one(
        {"patientID": patient_id},
        {"$set": {"medicalRecords": medical_records.dict()}}
    )
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Medical records updated successfully"}

# API: Add a new condition to a patient's medical records
@app.post("/api/v1/patients/{patient_id}/medical-records/conditions")
def add_condition(patient_id: str, condition: Condition):
    condition_data = condition.dict()
    update_result = patients_collection.update_one(
        {"patientID": patient_id},
        {"$push": {"medicalRecords.conditions": condition_data}}
    )
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Condition added successfully"}

# API: Add a new medication to a patient's medical records
@app.post("/api/v1/patients/{patient_id}/medical-records/medications")
def add_medication(patient_id: str, medication: Medication):
    medication_data = medication.dict()
    update_result = patients_collection.update_one(
        {"patientID": patient_id},
        {"$push": {"medicalRecords.medications": medication_data}}
    )
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Medication added successfully"}

# API: Add a new observation to a patient's medical records
@app.post("/api/v1/patients/{patient_id}/medical-records/observations")
def add_observation(patient_id: str, observation: Observation):
    observation_data = observation.dict()
    update_result = patients_collection.update_one(
        {"patientID": patient_id},
        {"$push": {"medicalRecords.observations": observation_data}}
    )
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Observation added successfully"}
