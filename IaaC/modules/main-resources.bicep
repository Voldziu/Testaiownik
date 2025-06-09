// Hybrid approach: Reference existing AI Foundry, create supporting resources
param location string
param environment string
param projectName string
param postgreSqlSku string
param dbAdminUsername string
@secure()
param dbAdminPassword string


param existingAiFoundryName string
param existingAiFoundryResourceGroup string 

// Variables
var dbServerName = '${projectName}-db-${environment}'
var dbName = '${projectName}_db'
var storageAccountName = replace('${projectName}st${environment}', '-', '')

// Reference existing AI Foundry resource (created manually)
resource existingAiFoundry 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: existingAiFoundryName
  scope: resourceGroup(existingAiFoundryResourceGroup)
}

// Storage Account for logs
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}



// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${projectName}-insights-${environment}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: 30
  }
}

// Azure AI Hub (connects to existing AI Foundry)
resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: '${projectName}-aihub-${environment}'
  location: location
  kind: 'Hub'
  properties: {
    friendlyName: '${projectName} AI Hub'
    description: 'AI Hub for TESTAIOWNIK project'
    storageAccount: storageAccount.id
    applicationInsights: appInsights.id
  }
  identity: {
    type: 'SystemAssigned'
  }
}


// Azure AI Project
resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: '${projectName}-project-${environment}'
  location: location
  kind: 'Project'
  properties: {
    friendlyName: '${projectName} Project'
    description: 'AI Project for TESTAIOWNIK'
    hubResourceId: aiHub.id
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// PostgreSQL Flexible Server
resource postgreSqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: dbServerName
  location: location
  sku: {
    name: postgreSqlSku
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: dbAdminUsername
    administratorLoginPassword: dbAdminPassword
    version: '15'
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// PostgreSQL Database
resource postgreSqlDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgreSqlServer
  name: dbName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.UTF8'
  }
}

// Firewall rule to allow Azure services
resource postgreSqlFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgreSqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Container App Environment
resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${projectName}-env-${environment}'
  location: location
  properties: {}
}



