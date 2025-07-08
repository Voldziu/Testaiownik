How to push docker changes:


az acr login --name testaiownik

# Frontend
docker build -t testaiownik.azurecr.io/testaiownik-frontend:latest -f src/Testaiownik/Frontend/Dockerfile .
docker push testaiownik.azurecr.io/testaiownik-frontend:latest

# Backend
docker build -t testaiownik.azurecr.io/testaiownik-backend:latest -f src/Testaiownik/Backend/Dockerfile .
docker push testaiownik.azurecr.io/testaiownik-backend:latest