# TechConf Registration Website

## Project Overview
The TechConf website allows attendees to register for an upcoming conference. Administrators can also view the list of attendees and notify all attendees via a personalized email message.

The application is currently working but the following pain points have triggered the need for migration to Azure:
 - The web application is not scalable to handle user load at peak
 - When the admin sends out notifications, it's currently taking a long time because it's looping through all attendees, resulting in some HTTP timeout exceptions
 - The current architecture is not cost-effective 

In this project, you are tasked to do the following:
- Migrate and deploy the pre-existing web app to an Azure App Service
- Migrate a PostgreSQL database backup to an Azure Postgres database instance
- Refactor the notification logic to an Azure Function via a service bus queue message

## Dependencies

You will need to install the following locally:
- [Postgres](https://www.postgresql.org/download/)
- [Visual Studio Code](https://code.visualstudio.com/download)
- [Azure Function tools V3](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Ccsharp%2Cbash#install-the-azure-functions-core-tools)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest)
- [Azure Tools for Visual Studio Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack)

## Project Instructions

### Part 1: Create Azure Resources and Deploy Web App
1. Create a Resource group
2. Create an Azure Postgres Database single server
   - Add a new database `techconfdb`
   - Allow all IPs to connect to database server
   - Restore the database with the backup located in the data folder
3. Create a Service Bus resource with a `notificationqueue` that will be used to communicate between the web and the function
   - Open the web folder and update the following in the `config.py` file
      - `POSTGRES_URL`
      - `POSTGRES_USER`
      - `POSTGRES_PW`
      - `POSTGRES_DB`
      - `SERVICE_BUS_CONNECTION_STRING`
4. Create App Service plan
5. Create a storage account
6. Deploy the web app

### Part 2: Create and Publish Azure Function
1. Create an Azure Function in the `function` folder that is triggered by the service bus queue created in Part 1.

      **Note**: Skeleton code has been provided in the **README** file located in the `function` folder. You will need to copy/paste this code into the `__init.py__` file in the `function` folder.
      - The Azure Function should do the following:
         - Process the message which is the `notification_id`
         - Query the database using `psycopg2` library for the given notification to retrieve the subject and message
         - Query the database to retrieve a list of attendees (**email** and **first name**)
         - Loop through each attendee and send a personalized subject message
         - After the notification, update the notification status with the total number of attendees notified
2. Publish the Azure Function

### Part 3: Refactor `routes.py`
1. Refactor the post logic in `web/app/routes.py -> notification()` using servicebus `queue_client`:
   - The notification method on POST should save the notification object and queue the notification id for the function to pick it up
2. Re-deploy the web app to publish changes

## Monthly Cost Analysis
Complete a month cost analysis of each Azure resource to give an estimate total cost using the table below:

### Monthly Cost Analysis (Estimate)

| Azure Resource | Tier / SKU | Estimated Monthly Cost | Usage Notes |
|---|---:|---:|---|
| Azure App Service (Web App) | F1 (Linux) | ~A$0 / month (region-dependent) | Hosts the Flask web application. Always-on web tier. |
| Azure Functions (Function App) | Functions v4 (Plan depends) | Varies (plan-based) | Runs the Service Bus-triggered worker to process notifications and update DB status. |
| Azure Database for PostgreSQL | Flexible Server Burstable B1ms (1 vCore, 2 GiB) + storage | Varies (compute + storage) | Stores attendees and notifications. SSL required. Storage size in this project ~32 GiB. |
| Azure Service Bus | Standard | Base charge ~0.0135/hour (~$9.86/month USD) + operations | Queue used for decoupling web request from notification processing. First 13M ops/month included. |
| Azure Storage Account | Standard_LRS | Small (typically a few dollars or less for this project) | Required by Azure Functions for internal storage (logs/leases/checkpoints). |

Notes: Costs vary by region and currency. Use Azure Pricing Calculator for exact estimates.

## Architecture Explanation

This project migrates a Flask-based conference registration web application to Azure using a decoupled, event-driven design.

The web application is hosted on Azure App Service (Web App). It provides the UI for registration and for creating email notifications. When a user submits a new notification, the web app writes the notification record to Azure Database for PostgreSQL and then publishes the notification ID to an Azure Service Bus queue.

Azure Service Bus acts as a reliable message broker between the web tier and the background processing tier. By queueing only the notification ID, the web app avoids long-running work during the HTTP request and remains responsive.

An Azure Function is subscribed to the Service Bus queue via a Service Bus trigger. When a message arrives, the function reads the notification_id from the message, queries PostgreSQL (via psycopg2) to retrieve the notification content and the attendee list, and then performs the notification processing. After processing, the function updates the notification status in PostgreSQL (for example, “Notified X attendees”) and records the completed timestamp.

This architecture improves scalability and reliability by separating user-facing requests from background processing. The web app can scale independently from the worker function, and Service Bus provides buffering/retry semantics in case the worker is temporarily unavailable.
