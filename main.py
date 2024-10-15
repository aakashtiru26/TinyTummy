import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import requests
import google.generativeai as genai  # Use the correct import for Gemini-1.5-Flash
from PIL import Image

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-adminsdk.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'tinytummy-13311.appspot.com'  # Use the correct bucket name without gs://
    })

# Access the storage bucket
storage_bucket = storage.bucket()

# Firestore database instance
db = firestore.client()

# Session states for user authentication and navigation
if 'user' not in st.session_state:
    st.session_state['user'] = None

if 'child_list' not in st.session_state:
    st.session_state['child_list'] = []

if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'intro'  # Track the current page

# Description about TinyTummy
def show_intro():
    st.markdown("""
    # Welcome to TinyTummy!
    
    TinyTummy is a child's nutrition tracker designed to help parents monitor their child's dietary habits effectively. 
    With our app, you can:
    
    - Track your child's meal intake.
    - Analyze nutritional values.
    - Set alerts for healthy eating.
    - Encourage a balanced diet with rewards!

    Sign up or log in to get started on the journey to better nutrition for your child!
    """)

    # Buttons for navigating to login and signup pages
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Log In"):
            st.session_state['current_page'] = 'login'
    with col2:
        if st.button("Sign Up"):
            st.session_state['current_page'] = 'sign_up'

# Sign Up page
def sign_up_page():
    st.title("TinyTummy: Sign Up")
    email = st.text_input("Email", placeholder="Enter your email")
    password = st.text_input("Password", placeholder="Enter your password", type="password")

    if st.button("Sign Up"):
        try:
            user = auth.create_user(email=email, password=password)
            # Create a document for the user with an empty children list
            db.collection('users').document(email).set({
                "children": []
            })
            st.success("User created successfully! Please log in.")
            st.session_state['current_page'] = 'intro'  # Redirect back to intro after sign-up
        except Exception as e:
            st.error(f"Error: {e}")

    # Add a button to go back to the login page
    if st.button("Already have an account? Log In"):
        st.session_state['current_page'] = 'login'

# Password reset function using Firebase REST API
def send_password_reset(email):
    api_key = "AIzaSyBWbLRwvrbk91igOR7RM5_nWtg5Bdt3huI"  # Your Firebase API key
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    data = {
        "requestType": "PASSWORD_RESET",
        "email": email
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise an error for bad responses
        st.success(f"Password reset email sent to {email}")
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get('error', {}).get('message', 'An error occurred')
        st.error(f"Error: {error_message}")

# Login page
def login_page():
    st.title("TinyTummy: Login")
    email = st.text_input("Email", placeholder="Enter your email")
    password = st.text_input("Password", placeholder="Enter your password", type="password")

    if st.button("Login"):
        try:
            user = auth.get_user_by_email(email)  # This will raise an error if the user doesn't exist
            if user:
                # Now verify the password using Firebase client-side (not available in Admin SDK)
                verify_password(email, password)  # Custom function to check password
        except auth.UserNotFoundError:
            st.error("User not found. Please sign up first.")
        except Exception as e:
            st.error(f"Error: {e}")

    # Add buttons to switch between login, signup, and reset password
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Create an Account"):
            st.session_state['current_page'] = 'sign_up'
    with col2:
        if st.button("Forgot Password"):
            if email:  # Check if email is provided
                send_password_reset(email)
            else:
                st.error("Please enter your email to reset your password.")  # Notify if email is missing
    with col3:
        if st.button("Back to Intro"):
            st.session_state['current_page'] = 'intro'

def verify_password(email, password):
    api_key = "AIzaSyBWbLRwvrbk91igOR7RM5_nWtg5Bdt3huI"
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    data = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise an error for bad responses
        st.session_state['user_email'] = email
        st.session_state['current_page'] = 'dashboard'  # Redirect to dashboard
        st.success("Login successful!")
        # Optionally fetch user data or child list
        user_doc = db.collection('users').document(email).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            st.session_state['child_list'] = user_data.get('children', [])
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get('error', {}).get('message', 'An error occurred')
        st.error(f"Invalid password. Error: {error_message}")

# Child details input page
def child_details_page():
    st.title("Enter Child Details")
    child_name = st.text_input("Child's Name")
    child_age = st.number_input("Child's Age", min_value=0, max_value=18)
    child_gender = st.selectbox("Child's Gender", ["Male", "Female", "Other"])

    if st.button("Submit"):
        if child_name and child_age >= 0 and child_gender:  # Check if all fields are filled
            new_child = {
                "child_name": child_name,
                "child_age": child_age,
                "child_gender": child_gender
            }
            st.session_state['child_list'].append(new_child)
            db.collection('users').document(st.session_state['user_email']).set({
                "children": st.session_state['child_list']
            })
            st.success("Child details saved successfully!")
            st.session_state['current_page'] = 'dashboard'
        else:
            st.error("Please fill in all fields.")

# User Account Details page with options to add, edit, or delete child details
def user_account_details():
    st.title("Account Details")

    if st.session_state['child_list']:
        st.write("Existing Child Details:")
        for idx, child in enumerate(st.session_state['child_list']):
            if 'child_name' in child and 'child_age' in child and 'child_gender' in child:  # Check if keys exist
                st.write(f"Child {idx+1}:")
                st.write(f"Name: {child['child_name']}, Age: {child['child_age']}, Gender: {child['child_gender']}")
                if st.button(f"Edit Child {idx+1}", key=f"edit_{idx}"):
                    st.session_state['current_page'] = f"edit_child_{idx}"
                if st.button(f"Delete Child {idx+1}", key=f"delete_{idx}"):
                    delete_child(idx)
            else:
                st.error(f"Error: Child data is incomplete for child {idx+1}.")

    if st.button("Add New Child"):
        st.session_state['current_page'] = 'add_new_child'

    if st.button("Back to Dashboard"):
        st.session_state['current_page'] = 'dashboard'

    if st.button("Log Out"):
        st.session_state['user_email'] = None
        st.session_state['current_page'] = 'intro'

# Edit child details
def edit_child_page(idx):
    child = st.session_state['child_list'][idx]
    st.title("Edit Child Details")

    child_name = st.text_input("Child's Name", value=child['child_name'])
    child_age = st.number_input("Child's Age", min_value=0, max_value=18, value=child['child_age'])
    child_gender = st.selectbox("Child's Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(child['child_gender']))

    if st.button("Save Changes"):
        st.session_state['child_list'][idx] = {
            "child_name": child_name,
            "child_age": child_age,
            "child_gender": child_gender
        }
        db.collection('users').document(st.session_state['user_email']).set({
            "children": st.session_state['child_list']
        })
        st.success("Child details updated successfully!")
        st.session_state['current_page'] = 'user_account_details'

    if st.button("Cancel"):
        st.session_state['current_page'] = 'user_account_details'

def delete_child(idx):
    st.session_state['child_list'].pop(idx)
    db.collection('users').document(st.session_state['user_email']).set({
        "children": st.session_state['child_list']
    })
    st.success("Child deleted successfully!")

def add_new_child_page():
    child_details_page()

api_key='AIzaSyAIMUJzYMflk5nB6TANPTOrXFoUR_Rr3HA'
genai.configure(api_key=api_key)

# Function to get the generative AI response
def get_gemini_response(input_prompt, image):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([input_prompt, image[0]])
    return response.text
# Function to prepare image for AI analysis
def input_image_setup(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        image_parts = [
            {
                "mime_type": uploaded_file.type,
                "data": bytes_data
            }
        ]
        return image_parts
    else:
        raise FileNotFoundError("No file uploaded")

# Dashboard page
def dashboard_page():
    st.title("Dashboard")
    st.write("Welcome to the Dashboard!")
    st.write("Here, you can track your child's meals and nutrition.")

    # Show child selection dropdown if there are child details stored
    if st.session_state['child_list']:
        st.subheader("Select Child")
        selected_child = st.selectbox("Choose the child to track meals for:", 
                                      options=st.session_state['child_list'], 
                                      format_func=lambda child: f"{child['child_name']} (Age: {child['child_age']}, Gender: {child['child_gender']})")
        
        # Display child details
        st.write(f"Tracking meals for {selected_child['child_name']} (Age: {selected_child['child_age']}, Gender: {selected_child['child_gender']})")

        # Image upload section
        st.subheader("Upload Meal Image")
        uploaded_image = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])

        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption="Uploaded Image.", use_column_width=True)

            # Reset the file pointer before analysis
            uploaded_image.seek(0)

            # Button to analyze the image
            if st.button("Tell me about the calories"):
                input_prompt = """
                You are an expert nutritionist where you need to see the food items from the image
                and calculate the total calories. Also provide the details of each food item with calories intake in the below format:

                1. Item 1 - number of calories
                2. Item 2 - number of calories
                ----
                Finally, mention whether the food is healthy, balanced, or not healthy and suggest additional healthy food items.
                """

                try:
                    image_data = input_image_setup(uploaded_image)
                    response = get_gemini_response(input_prompt, image_data)
                    st.write(response)
                except Exception as e:
                    st.error(f"Error analyzing the image: {e}")

            # Reset the file pointer before uploading to Firebase
            uploaded_image.seek(0)

            # Create a file name/path based on child's details
            file_name = f"{selected_child['child_name']}_age_{selected_child['child_age']}_gender_{selected_child['child_gender']}/{uploaded_image.name}"
            blob = storage_bucket.blob(f"meal_images/{file_name}")

            # Upload file to Firebase Storage
            try:
                blob.upload_from_file(uploaded_image)
                st.success(f"Image uploaded to Firebase under {file_name}")
            except Exception as e:
                st.error(f"Error uploading the image: {e}")

    else:
        st.error("No child details found. Please add child details first.")

    # Add options to navigate to account details or logout
    if st.button("Go to Account Details"):
        st.session_state['current_page'] = 'user_account_details'
    if st.button("Log Out"):
        st.session_state['user_email'] = None
        st.session_state['current_page'] = 'intro'


# Main application logic
def main():
    if st.session_state['current_page'] == 'intro':
        show_intro()
    elif st.session_state['current_page'] == 'sign_up':
        sign_up_page()
    elif st.session_state['current_page'] == 'login':
        login_page()
    elif st.session_state['current_page'] == 'child_details':
        child_details_page()
    elif st.session_state['current_page'] == 'user_account_details':
        user_account_details()
    elif st.session_state['current_page'].startswith('edit_child_'):
        idx = int(st.session_state['current_page'].split('_')[-1])
        edit_child_page(idx)
    elif st.session_state['current_page'] == 'add_new_child':
        add_new_child_page()
    elif st.session_state['current_page'] == 'dashboard':
        dashboard_page()

if __name__ == "__main__":
    main()
