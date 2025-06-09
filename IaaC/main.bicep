// Main Bicep template for deploying Azure resources for the AI project
targetScope = 'subscription'

@description('Localization')
param location string = 'swedencentral'

@description('Dev name (dev, test, prod)')
param environment string = 'dev'

@description('Project name')
param projectName string = 'testaiownik'



@description('SKUR for PostgreSQL')
param postgreSqlSku string = 'Standard_B1ms'

@description('Admin username for the database')
param dbAdminUsername string = 'dawid'

@description('Admin password for the database')
@secure()
param dbAdminPassword string

@description('Name of existing AI Foundry resource')
param existingAiFoundryName string

@description('Resource group of existing AI Foundry (optional)')
param existingAiFoundryResourceGroup string = ''

// RG creation
resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: '${projectName}-${environment}'
  location: location
}

// Deploy main resources
module mainResources 'modules/main-resources.bicep' = {
  name: 'main-resources-deployment'
  scope: rg
  params: {
    location: location
    environment: environment
    projectName: projectName
    postgreSqlSku: postgreSqlSku
    dbAdminUsername: dbAdminUsername
    dbAdminPassword: dbAdminPassword
    existingAiFoundryName: existingAiFoundryName
    existingAiFoundryResourceGroup: existingAiFoundryResourceGroup
  }
}

// Outputs
output resourceGroupName string = rg.name

