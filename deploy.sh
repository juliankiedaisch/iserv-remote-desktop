#!/bin/bash
cd backend/
docker build -t teacherki/mdg-desktop-backend:latest .
docker push teacherki/mdg-desktop-backend:latest
cd ..
cd frontend/
docker build -t teacherki/mdg-desktop-frontend:latest .
docker push teacherki/mdg-desktop-frontend:latest
