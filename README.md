# NetraSetu

### AI-Based Face Recognition Attendance System with Smart Dashboard and AI Chatbot

## Overview

NetraSetu is an intelligent attendance management system that automates the process of recording student attendance using face recognition technology. The system eliminates the need for manual attendance registers and provides a reliable, fast, and secure way to track student presence in classrooms.

The application is designed for educational institutions and integrates computer vision, a database management system, and an interactive dashboard to manage attendance records efficiently. In addition, an AI chatbot is included to assist users with basic queries related to attendance and system usage.

## Key Features

* **Face Recognition Attendance** – Automatically detects and recognizes student faces to mark attendance.
* **Student Registration System** – Allows administrators to register students along with their facial images.
* **Automated Roll Number Generation** – Generates roll numbers based on admission year, branch, and section.
* **Admin, Teacher, and Student Panels** – Separate interfaces for different types of users.
* **Attendance Dashboard** – Provides insights and statistics about attendance records.
* **Attendance Reports** – Generates attendance reports that can be exported or analyzed.
* **AI Chatbot Assistance** – A chatbot that helps users interact with the system and get quick information.
* **Secure Authentication System** – Login system for administrators, teachers, and students.
* **Scalable Architecture** – Modular code structure for easy extension and maintenance.

## Technology Stack

The system is built using the following technologies:

* **Programming Language:** Python
* **Frontend Interface:** Streamlit
* **Backend Services:** Flask
* **Computer Vision:** OpenCV
* **Face Recognition Model:** ArcFace-based embeddings
* **Database:** SQLite / MySQL
* **Data Processing:** Pandas
* **AI Chatbot Integration:** GROQ API
* **Version Control:** Git & GitHub

## System Architecture

The architecture of NetraSetu follows a modular structure consisting of multiple functional components:

1. **User Interface Layer** – Developed using Streamlit for interactive dashboards and system controls.
2. **Application Logic Layer** – Handles authentication, student management, and attendance processing.
3. **Face Recognition Engine** – Detects and identifies faces from camera input using trained recognition models.
4. **Database Layer** – Stores user data, student information, and attendance records.
5. **Chatbot Integration** – Uses an external AI API to provide assistance within the system.

These components work together to provide a seamless and automated attendance management workflow.

## Face Detection and Recognition Models

To ensure accurate and reliable face recognition, the system uses advanced deep learning–based face detection and recognition models.

### Face Detection Models

The following models are used for detecting faces from camera input before recognition:

**RetinaFace**
RetinaFace is a deep learning–based face detection model that provides highly accurate face localization along with facial landmark detection. It helps in detecting faces even under challenging conditions such as different lighting, angles, and partial occlusions.

**SCRFD (Sample and Computation Redistribution for Face Detection)**
SCRFD is a lightweight and efficient face detection model designed for real-time applications. It provides fast detection speed while maintaining high accuracy, making it suitable for live camera-based attendance systems.

**YOLOv5 Face**
YOLOv5 Face is a modified version of the YOLOv5 object detection model specifically optimized for face detection. It enables rapid detection of faces in real-time video streams and helps improve system responsiveness.

### Face Recognition Model

**ArcFace**
ArcFace is a state-of-the-art face recognition model that generates discriminative facial embeddings. It uses an additive angular margin loss to improve the separation between different identities. In this system, ArcFace is used to extract facial features from detected faces and match them with stored embeddings in the database to accurately identify students.


## Project Structure

```
NetraSetu/
│
├── main.py
├── admin_panel.py
├── teacher_panel.py
├── student_panel.py
├── attendance_system.py
├── database.py
├── utils.py
├── chatbot.py
├── sms_gateway.py
│
├── face_detection/
├── face_recognition/
├── face_alignment/
│
├── .streamlit/
│   └── config files
│
└── README.md
```

## Installation and Setup

### 1. Create a Virtual Environment

```
python -m venv venv
```

Activate the environment:

**Windows**

```
venv\Scripts\activate
```

**Linux / Mac**

```
source venv/bin/activate
```

### 2. Install Required Dependencies

```
pip install -r requirements.txt
```

### 3. Configure API Key

Create a file named `secrets.toml` inside the `.streamlit` folder and add your API key:

```
GROQ_API_KEY="your_api_key_here"
```

For security reasons, this file is not included in the repository.

### 4. Run the Application

Start the Streamlit application using the following command:

```
streamlit run main.py
```

The application will open automatically in your web browser.

## How the System Works

1. The administrator registers students along with their facial images.
2. The system processes these images and generates facial embeddings.
3. When a student appears in front of the camera, the system detects and recognizes the face.
4. If the identity matches the registered database, the attendance is recorded automatically.
5. Attendance records are stored in the database and can be viewed through the dashboard.

## Applications

* Educational institutions and colleges
* Training centers
* Smart classroom systems
* Automated attendance monitoring

## Future Enhancements

The system can be extended with additional features such as:

* Real-time notification system
* Mobile application integration
* Cloud-based database deployment
* Multi-camera support
* Advanced analytics and reporting

## License

This project is developed for academic and educational purposes as part of a final-year B.Tech project.


## Usage and Contribution

This project is developed for educational and research purposes. Anyone is welcome to explore, learn from, or build upon this project.

If you use this project or any part of the code in your own work, please provide proper credit to the original author and repository.

Contributions and improvements are welcome through pull requests.

## License

This project is released under the **SKIT College**.

You are free to use, modify, and distribute the code for educational or research purposes, provided that the original author and repository are properly acknowledged.

## Author

Rahul Prajapat
B.Tech – Artificial Intelligence

