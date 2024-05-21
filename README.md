
# FastAPI

Using FastAPI to perform the backend operations and establishing the connection between the UI and Database



## Acknowledgements

## Prerequisites

- Python 3.7+
- MySQL database


## Installation

VS code (1.89.1)
MySQL Workbench
Postman

CMD-
fastapi[all]
mysql connector - python 

*Clone the repository*:

    bash
    git clone https://github.com/yourusername/fastapi-auth.git
    cd fastapi-auth
    

*Create a virtual environment and activate it*:

    bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    

*Install the dependencies*:

    bash
    pip install fastapi uvicorn sqlalchemy databases pymysql passlib[bcrypt] python-jose python-multipart

*Set up the MySQL database*:

    - Install MySQL and create a new database:

        sql
        CREATE DATABASE fastapi_auth;
        CREATE USER 'fastapi_user'@'localhost' IDENTIFIED BY 'password';
        GRANT ALL PRIVILEGES ON fastapi_auth.* TO 'fastapi_user'@'localhost';
        FLUSH PRIVILEGES;
![Logo](https://fastapi.tiangolo.com/.png)


## Configuration


1. **Update the DATABASE_URL in database.py** to match your MySQL credentials:

    python
    DATABASE_URL = "mysql+pymysql://fastapi_user:password@localhost/fastapi_auth"
    

2. **Update the SECRET_KEY in auth.py**:

    python
    SECRET_KEY = "your_secret_key"
    
## Documentation

## Configuration

1. **Update the DATABASE_URL in database.py** to match your MySQL credentials:

    python
    DATABASE_URL = "mysql+pymysql://fastapi_user:password@localhost/fastapi_auth"
    

2. **Update the SECRET_KEY in auth.py**:

    python
    SECRET_KEY = "your_secret_key"


## Environment Variables

To run this project, you will need to add the following environment variables to your .env file

`API_KEY`

`ANOTHER_API_KEY`

`DATABASE_URL`

`SECRET_KEY`

`ENVIRONMENT`


## API Reference

#### Get all items

```http
  GET /api/items
```

| Parameter | Type     | Description                |
| :-------- | :------- | :------------------------- |
| `api_key` | `string` | **Required**. Your API key |

#### Get item

```http
  GET /api/items/${id}
```

| Parameter | Type     | Description                       |
| :-------- | :------- | :-------------------------------- |
| `id`      | `string` | **Required**. Id of item to fetch |

#### add(num1, num2)

Takes two numbers and returns the sum.



## 🔗 Links
https://github.com/WhiteboxHub/wbl-backend

## Features

- Light/dark mode toggle
- Live previews
- Fullscreen mode
- Cross platform


## License

[MIT](https://choosealicense.com/licenses/mit/)


## Running the Application


1. *Start the FastAPI application*:

    bash
    uvicorn main:app --reload

    
2. *Access the API documentation* at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
### User Registration

- *Endpoint*: POST /users/
- *Request Body*:

    json
    {
        "username": "yourusername",
        "email": "youremail@example.com",
        "password": "yourpassword"
    }
    

- *Response*:

    json
    {
        "id": 1,
        "username": "yourusername",
        "email": "youremail@example.com"
    }
    



## Token Generation


- *Endpoint*: POST /token
- *Request Body*: (as x-www-form-urlencoded)

    text
    username=yourusername&password=yourpassword
    

- *Response*:

    json
    {
        "access_token": "your_access_token",
        "token_type": "bearer"
    }
    

## Protected End point

- *Endpoint*: GET /recordings
- *Headers*:

    text
    Authorization: Bearer your_access_token
    

- *Response*: (Example)

    json
    [
        {
            "id": 1,
            "name": "Recording 1",
            "url": "http://example.com/recording1"
        }
    ]
    

## Using Postman


### Step 1: Acquire the Token

1. *Create a new request* in Postman.
2. *Set the request type* to POST.
3. *Enter the URL*: http://127.0.0.1:8000/token.
4. **Navigate to the Body tab** and select x-www-form-urlencoded.
5. *Add the following key-value pairs*:
    - username: yourusername
    - password: yourpassword
6. *Send the request*.
7. **Copy the access_token** from the response.

### Step 2: Use the Token to Access Protected Endpoints

1. *Create a new request* in Postman.
2. *Set the request type* to GET.
3. *Enter the URL*: http://127.0.0.1:8000/recordings.
4. **Navigate to the Authorization tab**.
5. **Select Bearer Token** from the Type dropdown.
6. **Paste the access_token** into the Token field.
7. *Send the request*.
8. *Inspect the response* to ensure you can access the protected resource.

## Troubleshooting

- Ensure that the SECRET_KEY in auth.py is kept secure and is not shared publicly.
- Verify that your MySQL database is running and accessible with the provided credentials.
- Check the FastAPI logs for any errors or warnings during requests.
- Make sure the token has not expired and is correctly formatted in the Authorization header.