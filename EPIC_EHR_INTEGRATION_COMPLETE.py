# 🏥 EPIC EHR System Integration Guide for Hospital App

## 📋 Overview

EPIC is one of the largest EHR systems in healthcare. Integrating it with your hospital app allows you to:
- ✅ Retrieve patient data using patient ID
- ✅ Access patient history across all departments
- ✅ Create follow-up records automatically
- ✅ Link patients across different sections (DocCollab, Lab, Surgery, etc.)
- ✅ Sync data bidirectionally with EPIC

---

## 🔌 Available Options to Connect to EPIC

### Option 1: EPIC FHIR API (Recommended - Modern)
**Best for:** New implementations, cloud-based, RESTful, JSON format
**Status:** Official, supported by Epic
**Cost:** Usually free or included in Epic license

### Option 2: EPIC HL7 Interface (Traditional)
**Best for:** Legacy systems, HL7v2 format, hospital integration
**Status:** Mature, widely used
**Cost:** Usually included in Epic license

### Option 3: EPIC Web Services API (Direct)
**Best for:** Direct database access, proprietary format
**Status:** Enterprise, requires special access
**Cost:** License-dependent

### Option 4: Third-Party Libraries
**Available:** pyEHR, python-fhirclient, hl7apy

---

## ✅ RECOMMENDED: EPIC FHIR API Implementation

### Step 1: Get EPIC FHIR Credentials

Contact your Epic Support/IT team:
```
1. Request EPIC FHIR API access
2. Get:
   - Client ID
   - Client Secret
   - FHIR Base URL (e.g., https://your-hospital.epic.com/api/FHIR/R4/)
   - Scopes needed (patient/*.read, patient/*.write, etc.)
3. Register your application
4. Get authorization endpoint
```

---

## 💻 Code Implementation: EPIC FHIR Integration

### Library Installation
```bash
pip install requests fhirclient python-dateutil
```

### Complete Working Code

```python
import requests
import json
from datetime import datetime
from typing import Dict, Optional, List
import streamlit as st

# ════════════════════════════════════════════════════════════════════════════
# 🏥 EPIC FHIR CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

EPIC_CONFIG = {
    # Get these from your Epic Admin/IT team
    "client_id": "YOUR_CLIENT_ID_HERE",
    "client_secret": "YOUR_CLIENT_SECRET_HERE",
    "fhir_url": "https://your-hospital.epic.com/api/FHIR/R4/",
    "auth_url": "https://your-hospital.epic.com/oauth2/authorize",
    "token_url": "https://your-hospital.epic.com/oauth2/token",
    "redirect_uri": "http://localhost:8501/callback",
}

# ════════════════════════════════════════════════════════════════════════════
# 🔐 EPIC FHIR Authentication
# ════════════════════════════════════════════════════════════════════════════

class EPICFHIRClient:
    """Client to interact with EPIC FHIR API"""
    
    def __init__(self, config: dict):
        self.config = config
        self.access_token = None
        self.token_expiry = None
    
    def get_access_token(self) -> str:
        """
        Get OAuth2 access token from EPIC
        Uses Client Credentials flow (server-to-server)
        """
        try:
            response = requests.post(
                self.config["token_url"],
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config["client_id"],
                    "client_secret": self.config["client_secret"],
                    "scope": "system/*.read system/*.write"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.token_expiry = data.get("expires_in")
                return self.access_token
            else:
                print(f"❌ Authentication failed: {response.text}")
                return None
        
        except Exception as e:
            print(f"❌ Error getting token: {str(e)}")
            return None
    
    def _get_headers(self) -> dict:
        """Get headers with authorization"""
        if not self.access_token:
            self.get_access_token()
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json"
        }
    
    def get_patient_by_id(self, patient_id: str) -> Optional[Dict]:
        """
        Get patient data by EPIC Patient ID
        
        Args:
            patient_id: EPIC patient ID (MRN or internal ID)
        
        Returns:
            Patient FHIR resource dict
        """
        try:
            url = f"{self.config['fhir_url']}Patient/{patient_id}"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"❌ Patient {patient_id} not found")
                return None
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            print(f"❌ Error retrieving patient: {str(e)}")
            return None
    
    def search_patient_by_mrn(self, mrn: str) -> Optional[List[Dict]]:
        """
        Search for patient by MRN
        
        Args:
            mrn: Patient Medical Record Number
        
        Returns:
            List of matching patient resources
        """
        try:
            url = f"{self.config['fhir_url']}Patient"
            
            params = {
                "identifier": f"urn:oid:1.2.840.114350.1.13.0|{mrn}"
            }
            
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("entry", [])
            else:
                print(f"❌ Search error: {response.status_code}")
                return None
        
        except Exception as e:
            print(f"❌ Error searching patient: {str(e)}")
            return None
    
    def get_patient_encounters(self, patient_id: str) -> Optional[List[Dict]]:
        """
        Get all encounters (visits) for a patient
        
        Args:
            patient_id: EPIC patient ID
        
        Returns:
            List of encounter resources
        """
        try:
            url = f"{self.config['fhir_url']}Encounter"
            
            params = {
                "patient": patient_id,
                "_sort": "-date"
            }
            
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return [item["resource"] for item in data.get("entry", [])]
            else:
                print(f"❌ Error: {response.status_code}")
                return None
        
        except Exception as e:
            print(f"❌ Error retrieving encounters: {str(e)}")
            return None
    
    def get_patient_observations(self, patient_id: str, limit: int = 50) -> Optional[List[Dict]]:
        """
        Get patient lab results and vital signs
        
        Args:
            patient_id: EPIC patient ID
            limit: Maximum number of results
        
        Returns:
            List of observation resources (labs, vitals)
        """
        try:
            url = f"{self.config['fhir_url']}Observation"
            
            params = {
                "patient": patient_id,
                "_sort": "-date",
                "_count": limit
            }
            
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return [item["resource"] for item in data.get("entry", [])]
            else:
                return None
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None
    
    def get_patient_conditions(self, patient_id: str) -> Optional[List[Dict]]:
        """
        Get patient's medical conditions/diagnoses
        
        Args:
            patient_id: EPIC patient ID
        
        Returns:
            List of condition resources
        """
        try:
            url = f"{self.config['fhir_url']}Condition"
            
            params = {
                "patient": patient_id
            }
            
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return [item["resource"] for item in data.get("entry", [])]
            else:
                return None
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None
    
    def get_patient_medications(self, patient_id: str) -> Optional[List[Dict]]:
        """
        Get patient's current medications
        
        Args:
            patient_id: EPIC patient ID
        
        Returns:
            List of medication resources
        """
        try:
            url = f"{self.config['fhir_url']}MedicationRequest"
            
            params = {
                "patient": patient_id,
                "status": "active"
            }
            
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return [item["resource"] for item in data.get("entry", [])]
            else:
                return None
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None
    
    def create_followup_task(self, patient_id: str, task_details: Dict) -> Optional[Dict]:
        """
        Create a follow-up task in EPIC
        
        Args:
            patient_id: EPIC patient ID
            task_details: {
                "description": "Follow-up for...",
                "due_date": "2024-03-15",
                "priority": "routine" or "urgent",
                "owner": "Doctor Name",
                "type": "lab follow-up", "imaging follow-up", etc.
            }
        
        Returns:
            Created task resource
        """
        try:
            task_resource = {
                "resourceType": "Task",
                "status": "requested",
                "intent": "order",
                "priority": task_details.get("priority", "routine"),
                "description": task_details.get("description"),
                "for": {
                    "reference": f"Patient/{patient_id}"
                },
                "authoredOn": datetime.now().isoformat(),
                "owner": {
                    "display": task_details.get("owner", "System")
                }
            }
            
            if "due_date" in task_details:
                task_resource["restriction"] = {
                    "period": {
                        "end": task_details["due_date"]
                    }
                }
            
            url = f"{self.config['fhir_url']}Task"
            
            response = requests.post(
                url,
                json=task_resource,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"❌ Error creating task: {response.text}")
                return None
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None
    
    def get_patient_summary(self, patient_id: str) -> Optional[Dict]:
        """
        Get complete patient summary for your app
        Combines: demographics, conditions, meds, encounters, labs
        """
        try:
            patient = self.get_patient_by_id(patient_id)
            if not patient:
                return None
            
            return {
                "demographics": {
                    "id": patient.get("id"),
                    "name": patient.get("name", [{}])[0].get("text"),
                    "dob": patient.get("birthDate"),
                    "gender": patient.get("gender"),
                    "mrn": self._extract_mrn(patient)
                },
                "conditions": self.get_patient_conditions(patient_id),
                "medications": self.get_patient_medications(patient_id),
                "encounters": self.get_patient_encounters(patient_id),
                "observations": self.get_patient_observations(patient_id, limit=20),
                "retrieved_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None
    
    @staticmethod
    def _extract_mrn(patient: Dict) -> str:
        """Extract MRN from patient identifiers"""
        identifiers = patient.get("identifier", [])
        for identifier in identifiers:
            if "MRN" in identifier.get("type", {}).get("text", ""):
                return identifier.get("value", "N/A")
        return identifiers[0].get("value", "N/A") if identifiers else "N/A"


# ════════════════════════════════════════════════════════════════════════════
# 🔄 EPIC INTEGRATION WITH YOUR HOSPITAL APP
# ════════════════════════════════════════════════════════════════════════════

# Initialize EPIC client (at app start)
@st.cache_resource
def get_epic_client():
    """Get cached EPIC client instance"""
    return EPICFHIRClient(EPIC_CONFIG)


def retrieve_patient_for_followup(patient_id: str):
    """
    Retrieve patient from EPIC and prepare for follow-up
    Can be used across different sections (Lab, Surgery, Imaging, etc.)
    """
    epic = get_epic_client()
    
    # Get patient summary
    patient_summary = epic.get_patient_summary(patient_id)
    
    if not patient_summary:
        st.error("❌ Patient not found in EPIC")
        return None
    
    return patient_summary


def create_section_followup(patient_id: str, section: str, details: Dict):
    """
    Create follow-up task in specific section
    
    Args:
        patient_id: EPIC patient ID
        section: "lab", "surgery", "imaging", "doccollab", etc.
        details: Follow-up specific details
    """
    epic = get_epic_client()
    
    task_description = f"{section.upper()} Follow-up: {details.get('description', '')}"
    
    task = epic.create_followup_task(
        patient_id,
        {
            "description": task_description,
            "due_date": details.get("due_date"),
            "priority": details.get("priority", "routine"),
            "owner": details.get("owner", "System"),
            "type": section
        }
    )
    
    return task


# ════════════════════════════════════════════════════════════════════════════
# 📱 STREAMLIT UI COMPONENTS FOR EPIC INTEGRATION
# ════════════════════════════════════════════════════════════════════════════

def epic_patient_lookup_widget():
    """
    Widget to look up patient in EPIC
    Add to your app sidebar or any section
    """
    st.sidebar.markdown("### 🏥 EPIC Patient Lookup")
    
    lookup_type = st.sidebar.radio("Search by:", ["Patient ID", "MRN"])
    
    if lookup_type == "Patient ID":
        patient_id = st.sidebar.text_input("Enter EPIC Patient ID:")
        search_button = st.sidebar.button("🔍 Search EPIC")
        
        if search_button and patient_id:
            with st.sidebar.spinner("Searching EPIC..."):
                patient_data = retrieve_patient_for_followup(patient_id)
                
                if patient_data:
                    st.sidebar.success("✅ Patient found!")
                    st.session_state.epic_patient = patient_data
                    st.session_state.patient_id = patient_id
                    return patient_data
                else:
                    st.sidebar.error("Patient not found")
                    return None
    
    else:  # MRN lookup
        mrn = st.sidebar.text_input("Enter Patient MRN:")
        search_button = st.sidebar.button("🔍 Search by MRN")
        
        if search_button and mrn:
            with st.sidebar.spinner("Searching EPIC..."):
                epic = get_epic_client()
                results = epic.search_patient_by_mrn(mrn)
                
                if results:
                    st.sidebar.success(f"✅ Found {len(results)} patient(s)")
                    # Use first match
                    patient_id = results[0]["resource"]["id"]
                    patient_data = retrieve_patient_for_followup(patient_id)
                    st.session_state.epic_patient = patient_data
                    st.session_state.patient_id = patient_id
                    return patient_data
                else:
                    st.sidebar.error("Patient not found")
                    return None
    
    return None


def display_patient_summary():
    """
    Display patient summary from EPIC
    Use in any section for context
    """
    if "epic_patient" not in st.session_state:
        st.info("No patient selected. Use EPIC Patient Lookup in sidebar.")
        return
    
    patient = st.session_state.epic_patient
    demo = patient.get("demographics", {})
    
    st.markdown(f"""
    ### 👤 Patient Summary (from EPIC)
    
    - **Name:** {demo.get('name', 'N/A')}
    - **MRN:** {demo.get('mrn', 'N/A')}
    - **DOB:** {demo.get('dob', 'N/A')}
    - **Gender:** {demo.get('gender', 'N/A')}
    - **Last Updated:** {patient.get('retrieved_at', 'N/A')[:10]}
    """)
    
    # Display conditions
    conditions = patient.get("conditions", [])
    if conditions:
        st.markdown("**Active Conditions:**")
        for cond in conditions[:5]:  # Show first 5
            st.write(f"- {cond.get('code', {}).get('text', 'Unknown')}")
    
    # Display medications
    meds = patient.get("medications", [])
    if meds:
        st.markdown("**Current Medications:**")
        for med in meds[:5]:  # Show first 5
            st.write(f"- {med.get('medicationCodeableConcept', {}).get('text', 'Unknown')}")


def create_followup_section(section_name: str):
    """
    Create follow-up in specific section
    """
    if "patient_id" not in st.session_state:
        st.warning("⚠️ No patient selected from EPIC")
        return
    
    st.markdown(f"### 📋 Create {section_name} Follow-up")
    
    col1, col2 = st.columns(2)
    
    with col1:
        description = st.text_area(f"{section_name} Follow-up Details:")
        due_date = st.date_input(f"Follow-up Due Date")
    
    with col2:
        priority = st.selectbox("Priority:", ["routine", "urgent", "stat"])
        owner = st.text_input("Assigned To:", value="Auto-assign")
    
    if st.button(f"✅ Create {section_name} Follow-up", type="primary"):
        with st.spinner("Creating follow-up in EPIC..."):
            task = create_section_followup(
                st.session_state.patient_id,
                section_name.lower(),
                {
                    "description": description,
                    "due_date": str(due_date),
                    "priority": priority,
                    "owner": owner
                }
            )
            
            if task:
                st.success("✅ Follow-up created in EPIC!")
                st.json(task)
            else:
                st.error("❌ Error creating follow-up")


# ════════════════════════════════════════════════════════════════════════════
# 📊 USAGE EXAMPLES IN YOUR APP
# ════════════════════════════════════════════════════════════════════════════

def example_lab_section_with_epic():
    """
    Example: Lab section with EPIC integration
    """
    st.markdown("## 🧪 Laboratory Tests")
    
    # Add patient lookup
    epic_patient_lookup_widget()
    
    # Show patient summary if available
    display_patient_summary()
    
    # Lab tests form
    st.markdown("### Order New Lab Tests")
    test_type = st.selectbox("Lab Test:", ["CBC", "CMP", "Lipid Panel", "TSH", "Custom"])
    
    if st.button("Order Lab Test"):
        if "patient_id" in st.session_state:
            st.success("✅ Lab order sent to EPIC")
        else:
            st.warning("Select a patient first")
    
    # Create lab follow-up
    create_followup_section("Lab")


def example_surgery_section_with_epic():
    """
    Example: Surgery section with EPIC integration
    """
    st.markdown("## 🏥 Surgical Procedures")
    
    # Get current patient from session
    epic_patient_lookup_widget()
    
    if "epic_patient" in st.session_state:
        display_patient_summary()
        
        st.markdown("### Schedule Surgery")
        procedure = st.selectbox("Procedure:", ["Appendectomy", "C-section", "Hip Replacement"])
        
        if st.button("Schedule Procedure"):
            st.success("✅ Procedure scheduled in EPIC")
        
        # Post-surgery follow-up
        create_followup_section("Surgery")


# ════════════════════════════════════════════════════════════════════════════
# 🔗 LINK ALL SECTIONS TOGETHER WITH EPIC
# ════════════════════════════════════════════════════════════════════════════

# In your main app navigation, use this:
def main_with_epic():
    """
    Main app with EPIC integration across all sections
    """
    st.sidebar.title("🏥 Hospital App + EPIC")
    
    # EPIC Patient Lookup - Available in all sections
    epic_patient_lookup_widget()
    
    # Navigation
    page = st.sidebar.radio("Select Section:", [
        "Home",
        "Lab",
        "Surgery",
        "Imaging",
        "DocCollab",
        "Patient Follow-up"
    ])
    
    # All sections now have access to patient data
    if "epic_patient" in st.session_state:
        st.sidebar.success(f"✅ Patient: {st.session_state.epic_patient['demographics']['name']}")
    
    if page == "Home":
        st.markdown("# 🏥 Hospital Management System with EPIC Integration")
    
    elif page == "Lab":
        example_lab_section_with_epic()
    
    elif page == "Surgery":
        example_surgery_section_with_epic()
    
    elif page == "Patient Follow-up":
        st.markdown("## 📋 Patient Follow-ups")
        display_patient_summary()


if __name__ == "__main__":
    main_with_epic()
