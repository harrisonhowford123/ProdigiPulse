import requests
from dataclasses import dataclass
from typing import List
import json
from datetime import datetime

# Define an Employee dataclass
@dataclass
class Employee:
    id: int
    employeeName: str
    password: str
    hourlyRate: float

@dataclass
class pulseEmployee:
    id: int
    employeeName: str
    password: str
    pulseAccess: list


target_ip = "192.168.111.230"

def fetch_pulse_employees(server_ip: str = target_ip, port: int = 8080) -> List[pulseEmployee]:

    url = f"http://{server_ip}:{port}/api/pulseEmployees"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            return []

        employees = []
        for emp in data.get("employees", []):
            pulse_access = emp.get("pulseAccess") or []  # handle None
            if not isinstance(pulse_access, list):
                pulse_access = []
            employees.append(pulseEmployee(
                id=emp.get("id"),
                employeeName=emp.get("employeeName"),
                password=emp.get("password"),
                pulseAccess=pulse_access
            ))
        return employees

    except requests.RequestException as e:
        print(f"Error fetching Pulse employees: {e}")
        return []

def fetch_manual_tasks(server_ip: str = target_ip, port: int = 8080) -> list[str]:
    url = f"http://{server_ip}:{port}/api/manualTasks"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            return []

        # Assume server returns: {"status":"success", "tasks":["task1","task2",...]}
        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        return [str(task) for task in tasks]

    except requests.RequestException as e:
        print(f"Error fetching manual tasks: {e}")
        return []


def fetch_tracking_history(orderNumber=None, leadBarcode=None, isoBarcode=None,
                           server_ip=target_ip, port=8080, debug=False):

    if not (orderNumber or leadBarcode or isoBarcode):
        return {"status": "error", "message": "Must provide at least one of orderNumber, leadBarcode, or isoBarcode"}

    url = f"http://{server_ip}:{port}/api/getTrackingHistory"
    payload = {
        "orderNumber": orderNumber,
        "leadBarcode": leadBarcode,
        "isoBarcode": isoBarcode
    }

    if debug:
        print("\n[DEBUG] === fetch_tracking_history() ===")
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload, timeout=10)

        if debug:
            print(f"[DEBUG] Response status: {response.status_code}")
            print(f"[DEBUG] Raw response text: {response.text[:500]}")  # avoid dumping huge responses

        response.raise_for_status()
        data = response.json()

        if debug:
            print(f"[DEBUG] Parsed JSON: {json.dumps(data, indent=2)}")

        if data.get("status") != "success":
            if debug:
                print(f"[DEBUG] Server returned error: {data.get('message', 'Unknown error')}")
            return {"status": "error", "message": data.get("message", "Unknown server error")}

        return {"status": "success", "history": data.get("history", [])}

    except requests.RequestException as e:
        if debug:
            print(f"[DEBUG] RequestException: {e}")
        return {"status": "error", "message": str(e)}

    except json.JSONDecodeError:
        if debug:
            print("[DEBUG] JSONDecodeError: Invalid JSON response from server")
        return {"status": "error", "message": "Invalid JSON response from server"}

def fetch_employees_tasks(server_ip=target_ip, port=8080):

    url = f"http://{server_ip}:{port}/api/employeesTasks"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            print(f"Server error: {data.get('message')}")
            return []

        return data.get("tasks", [])

    except requests.RequestException as e:
        print(f"Error fetching employees tasks: {e}")
        return []


def update_employee_task(employeeName, liveTask=None, status=None, isobarcode=None, erase=False, 
                        server_ip=target_ip, port=8080):

    if not employeeName:
        return {"status": "error", "message": "employeeName is required"}

    url = f"http://{server_ip}:{port}/api/updateEmployeeTask"
    payload = {
        "employeeName": employeeName,
        "liveTask": liveTask,
        "status": status,
        "isobarcode": isobarcode,
        "erase": erase
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON response from server"}

def fetch_all_employees(server_ip=target_ip, port=8080) -> List[Employee]:
    url = f"http://{server_ip}:{port}/api/employees"
    try:
        response = requests.get(url, timeout=10)  # Add timeout to prevent indefinite hang
        response.raise_for_status()  # Raise an error for HTTP errors

        data = response.json()

        if data.get("status") != "success":
            return []

        employee_list = []
        for emp in data.get("employees", []):
            employee_list.append(Employee(
                id=emp.get("id"),
                employeeName=emp.get("employeeName"),
                password=emp.get("password"),
                hourlyRate=emp.get("hourlyRate")
            ))

        return employee_list

    except requests.RequestException:
        return []

def add_facility_workstation(workstation_name, addElse=False, server_ip=target_ip, port=8080):
    if not workstation_name:
        return {"status": "error", "message": "workstationName is required"}

    url = f"http://{server_ip}:{port}/api/addFacilityWorkstation"
    payload = {
        "workstationName": workstation_name,
        "addElse": addElse
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON response from server"}

def edit_tasks(taskName: str, editFlag: bool, server_ip: str = target_ip, port: int = 8080, debug: bool = False) -> dict:

    if not taskName:
        return {"status": "error", "message": "taskName is required"}
    if not isinstance(editFlag, bool):
        return {"status": "error", "message": "editFlag must be a boolean"}

    url = f"http://{server_ip}:{port}/api/editTasks"
    payload = {"taskName": taskName, "editFlag": editFlag}

    if debug:
        print("\n[DEBUG] === edit_tasks() ===")
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload, timeout=10)

        if debug:
            print(f"[DEBUG] Response status: {response.status_code}")
            print(f"[DEBUG] Raw response text: {response.text[:500]}")  # prevent huge dumps

        response.raise_for_status()
        data = response.json()

        if debug:
            print(f"[DEBUG] Parsed JSON: {json.dumps(data, indent=2)}")

        if data.get("status") != "success":
            return {"status": "error", "message": data.get("message", "Unknown server error")}

        return data

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON response from server"}


def log_employee_time(employeeName: str, logged_in: datetime, duration: str,
                      server_ip=target_ip, port=8080):

    if not employeeName:
        return {"status": "error", "message": "employeeName is required"}

    url = f"http://{server_ip}:{port}/api/logEmployeeTime"

    payload = {
        "employeeName": employeeName,
        "logged_in": logged_in.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": duration
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        resp_json = response.json()
        return resp_json

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON response from server"}

def removeWorkstation(employee_name: str, workstation_name: str,
                      server_ip= target_ip, port= 8080):
    
    url = f"http://{server_ip}:{port}/api/removeWorkstation"
    payload = {
        "employeeName": employee_name,
        "workstationName": workstation_name
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            print(f"[WARN] Server returned error: {data}")
        else:
            print(f"[INFO] Successfully removed '{employee_name}' from '{workstation_name}'")
        return data
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to call removeWorkstation: {e}")
        return {"status": "error", "message": str(e)}

def fetch_employee_start_time(employee_name, server_ip=target_ip, port=8080):

    url = f"http://{server_ip}:{port}/api/getEmployeeStartTime"
    payload = {"employeeName": employee_name}

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            start_time_str = data.get("start_time")
            if start_time_str:
                return datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            else:
                print(f"[Client] Employee '{employee_name}' has no start_time set.")
                return None
        else:
            print(f"[Client] Error: {data.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[Client] Connection error: {e}")
        return None

def loggedOut(employeeName: str, server_ip=target_ip, port=8080):
    if not employeeName:
        return {"status": "error", "message": "employeeName is required"}

    url = f"http://{server_ip}:{port}/api/loggedOut"
    payload = {
        "status": "LoggedOut",
        "employeeName": employeeName
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()  # Return server response as JSON
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON response from server"}

def add_or_update_employee(employeeName, password=None, hourlyRate=None, workstation_list=None,
                           server_ip=target_ip, port=8080):
    """
    Sends a POST request to the server to add or update an employee.
    """
    if not employeeName:
        return {"status": "error", "message": "employeeName is required"}

    url = f"http://{server_ip}:{port}/api/addOrUpdateEmployee"
    
    # Prepare JSON payload
    payload = {
        "employeeName": employeeName,
        "password": password,
        "hourlyRate": hourlyRate,
        "workstations": workstation_list or []
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        resp_json = response.json()
        return resp_json

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": "Invalid JSON response from server"}


def fetch_next_container_id(server_ip=target_ip, port=8080):
    url = f"http://{server_ip}:{port}/api/nextContainerID"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data.get("nextContainerID")
        else:
            print(f"Server error: {data.get('message')}")
            return None

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

def remove_employee(employeeName, server_ip=target_ip, port=8080):
    """
    Request server to remove an employee by name. Server handles table updates.
    """
    if not employeeName:
        return {"status": "error", "message": "No employee name provided"}

    url = f"http://{server_ip}:{port}/api/removeEmployee"
    try:
        resp = requests.post(url, json={"employeeName": employeeName})
        resp.raise_for_status()
        return resp.json()

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}


def get_facility_workstations(server_ip=target_ip, port=8080):
    workstations = []
    availableStations = []
    eligibleList = []

    url = f"http://{server_ip}:{port}/api/facilityWorkstations"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        # Expecting data to contain keys: workstations, availableStations, eligibleList
        workstations = data.get("workstations") or []
        availableStations = data.get("availableStations") or []
        eligibleList = data.get("eligibleList") or []

    except requests.RequestException as e:
        print(f"[ERROR] Could not fetch facility workstations: {e}")
    except ValueError as e:
        # JSON decoding error
        print(f"[ERROR] Invalid JSON response: {e}")

    return workstations, availableStations, eligibleList


def send_tracking_data(containerID, orderNumber, leadBarcode, isoBarcode, workstation, employeeName,
                       server_ip=target_ip, port=8080):

    base_url = f"http://{server_ip}:{port}"
    params = {
        "containerID": containerID,
        "orderNumber": orderNumber,
        "leadBarcode": leadBarcode,
        "isoBarcode": isoBarcode,
        "workstation": workstation,
        "employeeName": employeeName
    }

    try:
        resp = requests.get(f"{base_url}/api/orderTrack", params=params)
        resp.raise_for_status()
        return resp.json()

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}

def move_container(leadBarcode=None, isoBarcode=None, workstation="", employeeName="",
                   server_ip=target_ip, port=8080):

    base_url = f"http://{server_ip}:{port}"
    params = {
        "leadBarcode": leadBarcode,
        "isoBarcode": isoBarcode,
        "workstation": workstation,
        "employeeName": employeeName
    }

    try:
        resp = requests.get(f"{base_url}/api/moveContainer", params=params)
        resp.raise_for_status()
        return resp.json()

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}

def fetch_facility_workstations(server_ip=target_ip, port=8080):
    url = f"http://{server_ip}:{port}/api/facilityWorkstations"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Extract the lists
        workstations = data.get("workstations", [])
        availableStations = data.get("availableStations", [])
        eligibleList = data.get("eligibleList", [])

        return workstations, availableStations, eligibleList

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return [], [], []

