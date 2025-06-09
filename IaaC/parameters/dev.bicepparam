// Parameters for the prod environment

using '../main.bicep'
param location = 'swedencentral'
param environment = 'dev'
param projectName = 'testaiownik'
param postgreSqlSku = 'Standard_B1ms'
param dbAdminUsername = 'dawid'
param dbAdminPassword = readEnvironmentVariable('DB_ADMIN_PASSWORD','jasper')
param existingAiFoundryName = 'ai-2726721103ai115316279290'
param existingAiFoundryResourceGroup = 'aiFoundry'
