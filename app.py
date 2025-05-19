import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
import os
import base64
import io
import json
import pickle
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

# Add this at the beginning of the file, right after the imports
# Enable more detailed error messages
import sys
import traceback

def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            traceback.print_exc(file=sys.stdout)
            if func.__name__ in ['update_metrics']:
                return "0", "0", "0", "0"
            elif func.__name__ in ['update_time_series', 'update_request_type_pie', 'update_country_bar_chart', 'update_age_group_chart']:
                # Return an empty figure
                return go.Figure()
            elif func.__name__ == 'update_statistics_table':
                return html.Div("Error loading statistics. Please check the console for details.")
            else:
                return dash.no_update
    return wrapper

# Initialize the Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# Set a secret key for the Flask server (IMPORTANT for Flask-Login)
import os
server.secret_key = os.urandom(24)  # Generate a random 24-byte key

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

# User class for authentication
class User(UserMixin):
    def __init__(self, id, username, password, email=None):
        self.id = id
        self.username = username
        self.password = password
        self.email = email

# User database - now we'll use a file to persist users
USER_DB_FILE = 'users.pickle'

# Function to load users from file
def load_users():
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")
    
    # Default users if file doesn't exist or there's an error
    return {
        'admin': {'id': 'admin', 'username': 'admin', 'password': 'password123', 'email': 'admin@example.com'},
        'user': {'id': 'user', 'username': 'user', 'password': 'password124', 'email': 'user@example.com'}
    }

# Function to save users to file
def save_users(users):
    try:
        with open(USER_DB_FILE, 'wb') as f:
            pickle.dump(users, f)
        return True
    except Exception as e:
        print(f"Error saving users: {e}")
        return False

# Load users
USERS = load_users()

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        user_data = USERS[user_id]
        return User(user_data['id'], user_data['username'], user_data['password'], user_data.get('email'))
    return None

# Country to continent mapping
country_to_continent = {
    'United States': 'North America',
    'Canada': 'North America',
    'Mexico': 'North America',
    'Brazil': 'South America',
    'Argentina': 'South America',
    'Chile': 'South America',
    'Colombia': 'South America',
    'Peru': 'South America',
    'United Kingdom': 'Europe',
    'France': 'Europe',
    'Germany': 'Europe',
    'Italy': 'Europe',
    'Spain': 'Europe',
    'Russia': 'Europe',
    'China': 'Asia',
    'Japan': 'Asia',
    'India': 'Asia',
    'South Korea': 'Asia',
    'Australia': 'Oceania',
    'New Zealand': 'Oceania',
    'Egypt': 'Africa',
    'South Africa': 'Africa',
    'Nigeria': 'Africa',
    'Kenya': 'Africa'
}

# Default continent for unknown countries
default_continent = 'Unknown'

# Load and process the data
def load_data():
    try:
        # Load from assets folder
        print("Loading dashboard_web_server_logs.csv from assets folder")
        df = pd.read_csv('assets/dashboard_web_server_logs.csv')
        
        # Print column names for debugging
        print("Columns in the dataset:", df.columns.tolist())
        
        # Check if timestamp column exists, if not try to find a date/time column
        if 'timestamp' not in df.columns:
            print("'timestamp' column not found, looking for alternative time columns")
            
            # Look for common time column names
            time_columns = ['date', 'time', 'datetime', 'Date', 'Time', 'DateTime', 'log_time', 'request_time']
            found_time_col = None
            
            for col in time_columns:
                if col in df.columns:
                    print(f"Found time column: {col}")
                    found_time_col = col
                    break
            
            # If a time column is found, rename it to timestamp
            if found_time_col:
                df = df.rename(columns={found_time_col: 'timestamp'})
            else:
                # If no time column is found, creating a synthetic timestamp
                print("No time column found, creating a synthetic timestamp")
                df['timestamp'] = pd.date_range(start='2023-01-01', periods=len(df), freq='H')
        
        # Ensure timestamp is datetime type
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            print("Converting timestamp to datetime")
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
        # Process the data - check if date columns already exist
        if 'date' not in df.columns:
            df['date'] = df['timestamp'].dt.date
        
        if 'hour' not in df.columns:
            df['hour'] = df['timestamp'].dt.hour
            
        if 'day' not in df.columns:
            df['day'] = df['timestamp'].dt.day_name()
            
        if 'month' not in df.columns:
            df['month'] = df['timestamp'].dt.month_name()
        
        # Ensure other required columns exist
        required_columns = ['country', 'request_type', 'age_group', 'continent']
        for col in required_columns:
            if col not in df.columns:
                print(f"Warning: '{col}' column not found in the dataset")
                # Instead of creating synthetic data, just add an "Unknown" column
                df[col] = "Unknown"
        
    except Exception as e:
        # If file not found or any other error, provide a clear error message
        print(f"Error loading data: {e}")
        print("Please ensure dashboard_web_server_logs.csv exists in the assets folder")
        # Create a minimal dataframe to prevent dashboard errors
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2023-01-01', periods=10),
            'country': ['Unknown'] * 10,
            'continent': ['Unknown'] * 10,
            'request_type': ['Unknown'] * 10,
            'age_group': ['Unknown'] * 10,
        })
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        df['day'] = df['timestamp'].dt.day_name()
        df['month'] = df['timestamp'].dt.month_name()
    
    return df

# Load the data
df = load_data()

# Define the app layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# Login page layout
login_layout = html.Div([
    html.Div([
        html.Img(src='/assets/logo.png', style={'height': '80px', 'marginBottom': '20px'}),
        html.H2('Web Log Analytics Dashboard', style={'textAlign': 'center', 'color': '#2c3e50'}),
        html.H3('Login', style={'textAlign': 'center', 'color': '#2c3e50'}),
        html.Div([
            html.Label('Username', style={'fontWeight': 'bold'}),
            dcc.Input(
                id='username-input',
                type='text',
                placeholder='Enter username',
                className='form-control'
            ),
            html.Label('Password', style={'fontWeight': 'bold', 'marginTop': '15px'}),
            dcc.Input(
                id='password-input',
                type='password',
                placeholder='Enter password',
                className='form-control'
            ),
            html.Button('Login', id='login-button', n_clicks=0, className='btn-primary'),
            html.Div(id='login-error', style={'color': 'red', 'marginTop': '10px'}),
            html.Div([
                html.P("Don't have an account?", style={'marginTop': '20px', 'textAlign': 'center'}),
                html.Button('Register', id='go-to-register', n_clicks=0, className='btn-secondary')
            ])
        ], className='login-form')
    ], className='login-container')
], className='login-page')

# Registration page layout
register_layout = html.Div([
    html.Div([
        html.Img(src='/assets/logo.png', style={'height': '80px', 'marginBottom': '20px'}),
        html.H2('Web Log Analytics Dashboard', style={'textAlign': 'center', 'color': '#2c3e50'}),
        html.H3('Register New Account', style={'textAlign': 'center', 'color': '#2c3e50'}),
        html.Div([
            html.Label('Username', style={'fontWeight': 'bold'}),
            dcc.Input(
                id='register-username',
                type='text',
                placeholder='Choose a username',
                className='form-control'
            ),
            html.Label('Email', style={'fontWeight': 'bold', 'marginTop': '15px'}),
            dcc.Input(
                id='register-email',
                type='email',
                placeholder='Enter your email',
                className='form-control'
            ),
            html.Label('Password', style={'fontWeight': 'bold', 'marginTop': '15px'}),
            dcc.Input(
                id='register-password',
                type='password',
                placeholder='Choose a password',
                className='form-control'
            ),
            html.Label('Confirm Password', style={'fontWeight': 'bold', 'marginTop': '15px'}),
            dcc.Input(
                id='register-confirm-password',
                type='password',
                placeholder='Confirm your password',
                className='form-control'
            ),
            html.Button('Register', id='register-button', n_clicks=0, className='btn-primary'),
            html.Div(id='register-error', style={'color': 'red', 'marginTop': '10px'}),
            html.Div(id='register-success', style={'color': 'green', 'marginTop': '10px'}),
            html.Div([
                html.P("Already have an account?", style={'marginTop': '20px', 'textAlign': 'center'}),
                html.Button('Back to Login', id='go-to-login', n_clicks=0, className='btn-secondary')
            ])
        ], className='login-form')
    ], className='login-container')
], className='login-page')

# Dashboard layout
dashboard_layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.Img(src='/assets/logo.png', style={'height': '50px', 'marginRight': '15px'}),
            html.H2('Web Log Analytics Dashboard', style={'margin': '0', 'color': '#2c3e50'})
        ], style={'display': 'flex', 'alignItems': 'center'}),
        html.Div([
            html.Button('Logout', id='logout-button', className='btn-secondary')
        ], style={'marginLeft': 'auto'})  # This pushes the logout button to the right
    ], className='header'),
    
    # Navigation
    html.Div([
        html.Div([
            html.Button([html.I(className="fas fa-home", style={'marginRight': '8px'}), 'Home'], 
                        id='nav-home', 
                        className='nav-link active'),
            html.Button([html.I(className="fas fa-map-marker-alt", style={'marginRight': '8px'}), 'Map'], 
                        id='nav-map', 
                        className='nav-link'),
            html.Button([html.I(className="fas fa-clock", style={'marginRight': '8px'}), 'Time Analysis'], 
                        id='nav-time', 
                        className='nav-link'),
            html.Button([html.I(className="fas fa-chart-bar", style={'marginRight': '8px'}), 'Request Types'], 
                        id='nav-requests', 
                        className='nav-link'),
            html.Button([html.I(className="fas fa-database", style={'marginRight': '8px'}), 'Data'], 
                        id='nav-data', 
                        className='nav-link')
        ], className='nav-links')
    ], className='navigation'),

    # Add a store component to track the current page
    dcc.Store(id='current-page', data='home'),
    
    # Main content
    html.Div([
        # Two-column layout
        html.Div([
            # Left column - Filters panel
            html.Div([
                html.H4('Filter Data', style={'marginBottom': '15px', 'marginTop': '0'}),
                
                # First set of filters
                html.Div([
                    html.Label('Continent', style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='continent-filter',
                        options=[{'label': continent, 'value': continent} for continent in sorted(df['continent'].unique())],
                        value=[],
                        multi=True,
                        placeholder='Select continents...',
                        className='filter-dropdown'
                    ),
                ], className='filter-group'),
                
                # Second set of filters
                html.Div([
                    html.Label('Country', style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='country-filter',
                        options=[{'label': country, 'value': country} for country in sorted(df['country'].unique())],
                        value=[],
                        multi=True,
                        placeholder='Select countries...',
                        className='filter-dropdown'
                    ),
                ], className='filter-group'),

                # Third set of filters
                html.Div([
                    html.Label('Age Group', style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='age-group-filter',
                        options=[{'label': age, 'value': age} for age in sorted(df['age_group'].unique())],
                        value=[],
                        multi=True,
                        placeholder='Select age groups...',
                        className='filter-dropdown'
                    ),
                ], className='filter-group'),
                
                # Fourth set of filters
                html.Div([
                    html.Label('Request Type', style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='request-type-filter',
                        options=[{'label': req, 'value': req} for req in sorted(df['request_type'].unique())],
                        value=[],
                        multi=True,
                        placeholder='Select request types...',
                        className='filter-dropdown'
                    ),
                ], className='filter-group'),
                
                # Date range
                html.Div([
                    html.Label('Date Range', style={'fontWeight': 'bold'}),
                    dcc.DatePickerRange(
                        id='date-range',
                        min_date_allowed=df['timestamp'].min().date() if pd.api.types.is_datetime64_any_dtype(df['timestamp']) else pd.to_datetime(df['timestamp'].min()).date(),
                        max_date_allowed=df['timestamp'].max().date() if pd.api.types.is_datetime64_any_dtype(df['timestamp']) else pd.to_datetime(df['timestamp'].max()).date(),
                        start_date=df['timestamp'].min().date() if pd.api.types.is_datetime64_any_dtype(df['timestamp']) else pd.to_datetime(df['timestamp'].min()).date(),
                        end_date=df['timestamp'].max().date() if pd.api.types.is_datetime64_any_dtype(df['timestamp']) else pd.to_datetime(df['timestamp'].max()).date(),
                        className='date-picker'
                    ),
                ], className='filter-group'),
                
                # Reset button
                html.Div([
                    html.Button('Reset Filters', id='reset-filters', className='btn-secondary reset-button')
                ], className='filter-group', style={'marginTop': '20px'}),
            ], className='filters-panel'),
            
            # Right column - Dashboard content
            html.Div([
                html.Div(id='dashboard-content', children=[
                    # Key metrics
                    html.Div([
                        html.Div([
                            html.H4('Total Requests', style={'color': 'white'}),
                            html.H2(id='total-requests', children='10,000', style={'color': 'white'}),
                        ], className='metric-card', style={'backgroundColor': '#e74c3c'}),
                        
                        html.Div([
                            html.H4('Demo Requests', style={'color': 'white'}),
                            html.H2(id='demo-requests', children='2,489', style={'color': 'white'}),
                        ], className='metric-card', style={'backgroundColor': '#2ecc71'}),
                        
                        html.Div([
                            html.H4('Job Placements', style={'color': 'white'}),
                            html.H2(id='job-placements', children='2,441', style={'color': 'white'}),
                        ], className='metric-card', style={'backgroundColor': '#3498db'}),
                        
                        html.Div([
                            html.H4('AI Assistant Requests', style={'color': '#2c3e50'}),
                            html.H2(id='ai-assistant-requests', children='2,506', style={'color': '#2c3e50'}),
                        ], className='metric-card', style={'backgroundColor': '#FFA500'})
                    ], className='metrics-container'),
                    
                    # Charts
                    html.Div([
                        html.Div([
                            html.H3('Request Volume Over Time'),
                            dcc.Graph(id='time-series-chart', config={'displayModeBar': False})
                        ], className='chart-container'),
                        
                        html.Div([
                            html.H3('Request Type Distribution'),
                            dcc.Graph(id='request-type-pie', config={'displayModeBar': False})
                        ], className='chart-container'),
                        
                        html.Div([
                            html.H3('Requests by Country'),
                            dcc.Graph(id='country-bar-chart', config={'displayModeBar': False})
                        ], className='chart-container'),
                        
                        html.Div([
                            html.H3('Requests by Age Group'),
                            dcc.Graph(id='age-group-chart', config={'displayModeBar': False})
                        ], className='chart-container'),
                    ], className='charts-grid'),
                    
                    # Statistics section
                    html.Div([
                        html.H3('Request Statistics'),
                        html.Div(id='statistics-table', className='stats-table')
                    ], className='statistics-section')
                ])
            ], className='dashboard-content')
        ], className='two-column-layout')
    ], className='main-content')
], className='dashboard-container')

# Callback for page routing
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')]
)
def display_page(pathname):
    if pathname == '/login' or pathname == '/':
        return login_layout
    elif pathname == '/register':
        return register_layout
    elif pathname == '/dashboard':
        # Check if user is authenticated (in a real app)
        # For demo purposes, we'll just return the dashboard
        return dashboard_layout
    else:
        return '404 Page Not Found'

# Navigation between login and register pages - FIXED VERSION
# Split into two separate callbacks to avoid the missing component error

# Callback for going to registration page
@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input('go-to-register', 'n_clicks')],
    prevent_initial_call=True
)
def navigate_to_register(register_clicks):
    if register_clicks and register_clicks > 0:
        return '/register'
    return dash.no_update

# Separate callback for going back to login
@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input('go-to-login', 'n_clicks')],
    prevent_initial_call=True
)
def navigate_to_login(login_clicks):
    if login_clicks and login_clicks > 0:
        return '/login'
    return dash.no_update

# Registration callback
@app.callback(
    [Output('register-error', 'children'),
    Output('register-success', 'children'),
    Output('url', 'pathname', allow_duplicate=True)],
    [Input('register-button', 'n_clicks')],
    [State('register-username', 'value'),
    State('register-email', 'value'),
    State('register-password', 'value'),
    State('register-confirm-password', 'value')],
    prevent_initial_call=True
)
def register_user(n_clicks, username, email, password, confirm_password):
    if n_clicks > 0:
        # Validate inputs
        if not username or not email or not password or not confirm_password:
            return "All fields are required.", "", dash.no_update
        
        if password != confirm_password:
            return "Passwords do not match.", "", dash.no_update
        
        # Check if username already exists
        if username in USERS:
            return f"Username '{username}' is already taken.", "", dash.no_update
        
        # Check if email already exists
        for user_id, user_data in USERS.items():
            if user_data.get('email') == email:
                return f"Email '{email}' is already registered.", "", dash.no_update
        
        # Create new user
        new_user = {
            'id': username,
            'username': username,
            'password': password,
            'email': email
        }
        
        # Add to users dictionary
        USERS[username] = new_user
        
        # Save users to file
        if save_users(USERS):
            # Redirect to login page after successful registration
            return "", "Registration successful! You can now log in.", "/login"
        else:
            return "Error saving user data. Please try again.", "", dash.no_update
    
    return dash.no_update, dash.no_update, dash.no_update

# Login callback
@app.callback(
    [Output('url', 'pathname', allow_duplicate=True),
    Output('login-error', 'children')],
    [Input('login-button', 'n_clicks')],
    [State('username-input', 'value'),
    State('password-input', 'value')],
    prevent_initial_call=True
)
def login(n_clicks, username, password):
    if n_clicks > 0:
        if username in USERS and USERS[username]['password'] == password:
            # In a real app, you would use login_user(User(username))
            user_data = USERS[username]
            user = User(user_data['id'], user_data['username'], user_data['password'], user_data.get('email'))
            login_user(user)
            return '/dashboard', ''
        else:
            return '/login', 'Invalid username or password'
    return dash.no_update, dash.no_update

# Logout callback
@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input('logout-button', 'n_clicks')],
    prevent_initial_call=True
)
def logout(n_clicks):
    if n_clicks:
        # In a real app, you would use logout_user()
        logout_user()
        return '/login'
    return dash.no_update

# Filter data function
def filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = df.copy()
    
    try:
        # Ensure timestamp is datetime type for filtering
        if not pd.api.types.is_datetime64_any_dtype(filtered_df['timestamp']):
            filtered_df['timestamp'] = pd.to_datetime(filtered_df['timestamp'], errors='coerce')
        
        # Convert string dates to datetime for comparison
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Apply date filter
        filtered_df = filtered_df[(filtered_df['timestamp'].dt.date >= start_date) & 
                                (filtered_df['timestamp'].dt.date <= end_date)]
        
        # Apply continent filter if selected
        if continents and 'continent' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['continent'].isin(continents)]
        
        # Apply country filter if selected
        if countries and 'country' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['country'].isin(countries)]
        
        # Apply age group filter if selected
        if age_groups and 'age_group' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['age_group'].isin(age_groups)]
        
        # Apply request type filter if selected
        if request_types and 'request_type' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['request_type'].isin(request_types)]
    
    except Exception as e:
        print(f"Error in filter_dataframe: {e}")
        # Return original dataframe if filtering fails
        return df
    
    return filtered_df

# Update metrics callback
@app.callback(
    [Output('total-requests', 'children'),
    Output('demo-requests', 'children'),
    Output('job-placements', 'children'),
    Output('ai-assistant-requests', 'children')],
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_metrics(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    total_requests = len(filtered_df)
    
    # Check if 'request_type' column exists
    if 'request_type' in filtered_df.columns:
        demo_requests = len(filtered_df[filtered_df['request_type'] == 'demo'])
        job_placements = len(filtered_df[filtered_df['request_type'] == 'job'])
        ai_assistant = len(filtered_df[filtered_df['request_type'] == 'ai_assistant'])
    else:
        demo_requests = job_placements = ai_assistant = 0
    
    return f"{total_requests:,}", f"{demo_requests:,}", f"{job_placements:,}", f"{ai_assistant:,}"

# Update time series chart callback
@app.callback(
    Output('time-series-chart', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_time_series(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    try:
        # Ensure timestamp is datetime type
        if not pd.api.types.is_datetime64_any_dtype(filtered_df['timestamp']):
            filtered_df['timestamp'] = pd.to_datetime(filtered_df['timestamp'], errors='coerce')
            
        # Group by date and count requests
        time_series_data = filtered_df.groupby(filtered_df['timestamp'].dt.date).size().reset_index(name='count')
        time_series_data.columns = ['date', 'count']
        
        # Create the figure
        fig = px.line(
            time_series_data, 
            x='date', 
            y='count',
            labels={'date': 'Date', 'count': 'Number of Requests'},
            template='plotly_white'
        )
        
        fig.update_layout(
            margin=dict(l=40, r=40, t=40, b=40),
            hovermode='closest',
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                title='Date',
                gridcolor='lightgray',
                showgrid=True
            ),
            yaxis=dict(
                title='Number of Requests',
                gridcolor='lightgray',
                showgrid=True
            ),
            height=300  # Set consistent height
        )
        
        return fig
    except Exception as e:
        print(f"Error in update_time_series: {e}")
        # Return an empty figure with an error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error loading time series data: {e}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(height=300)  # Set consistent height
        return fig

# Update request type pie chart callback
@app.callback(
    Output('request-type-pie', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_request_type_pie(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    try:
        # Check if request_type column exists
        if 'request_type' not in filtered_df.columns:
            raise ValueError("'request_type' column not found in the dataset")
            
        # Group by request type and count
        request_type_counts = filtered_df['request_type'].value_counts().reset_index()
        request_type_counts.columns = ['request_type', 'count']
        
        # Create the figure
        fig = px.pie(
            request_type_counts, 
            values='count', 
            names='request_type',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        fig.update_layout(
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=300  # Set consistent height
        )
        
        fig.update_traces(textinfo='percent+label')
        
        return fig
    except Exception as e:
        print(f"Error in update_request_type_pie: {e}")
        # Return an empty figure with an error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error loading request type data: {e}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(height=300)  # Set consistent height
        return fig

@app.callback(
    Output('country-bar-chart', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_country_bar_chart(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    try:
        # Check if country column exists
        if 'country' not in filtered_df.columns:
            raise ValueError("'country' column not found in the dataset")
            
        # Group by country and count
        country_counts = filtered_df['country'].value_counts().reset_index()
        country_counts.columns = ['country', 'count']
        
        # Sort by count and take top 10
        country_counts = country_counts.sort_values('count', ascending=False).head(10)
        
        # Create the figure
        fig = px.bar(
            country_counts, 
            x='count', 
            y='country',
            orientation='h',
            labels={'count': 'Number of Requests', 'country': 'Country'},
            color='count',
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(
            margin=dict(l=20, r=20, t=30, b=20),
            plot_bgcolor='white',
            paper_bgcolor='white',
            yaxis=dict(
                title='',
                autorange='reversed'  # Highest value at the top
            ),
            xaxis=dict(
                title='Number of Requests',
                gridcolor='lightgray',
                showgrid=True
            ),
            coloraxis_showscale=False,
            height=300  # Set consistent height
        )
        
        return fig
    except Exception as e:
        print(f"Error in update_country_bar_chart: {e}")
        # Return an empty figure with an error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error loading country data: {e}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(height=300)  # Set consistent height
        return fig

# Update age group chart callback
@app.callback(
    Output('age-group-chart', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_age_group_chart(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Group by age group and count
    age_group_counts = filtered_df['age_group'].value_counts().reset_index()
    age_group_counts.columns = ['age_group', 'count']
    
    # Define the correct order for age groups
    age_order = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
    
    # Sort by the defined order
    age_group_counts['age_group'] = pd.Categorical(age_group_counts['age_group'], categories=age_order, ordered=True)
    age_group_counts = age_group_counts.sort_values('age_group')
    
    # Create the figure
    fig = px.bar(
        age_group_counts, 
        x='age_group', 
        y='count',
        labels={'count': 'Number of Requests', 'age_group': 'Age Group'},
        color='count',
        color_continuous_scale='Teal'
    )
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(
            title='Age Group',
            gridcolor='lightgray',
            showgrid=False
        ),
        yaxis=dict(
            title='Number of Requests',
            gridcolor='lightgray',
            showgrid=True
        ),
        coloraxis_showscale=False,
        height=300  # Set consistent height
    )
    
    return fig

# Update statistics table callback
@app.callback(
    Output('statistics-table', 'children'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_statistics_table(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Calculate statistics by request type
    stats = []
    for req_type in filtered_df['request_type'].unique():
        req_df = filtered_df[filtered_df['request_type'] == req_type]
        
        # Group by hour and count requests
        hourly_counts = req_df.groupby('hour').size().reset_index(name='count')
        
        # Calculate mean and standard deviation
        mean_requests = hourly_counts['count'].mean()
        std_requests = hourly_counts['count'].std()
        
        # Find peak hour
        peak_hour = hourly_counts.loc[hourly_counts['count'].idxmax(), 'hour']
        
        stats.append({
            'Request Type': req_type,
            'Total Requests': len(req_df),
            'Mean Requests per Hour': f"{mean_requests:.2f}",
            'Standard Deviation': f"{std_requests:.2f}",
            'Peak Hour': f"{peak_hour}:00"
        })
    
    # Create the table
    if stats:
        table_header = [
            html.Thead(html.Tr([
                html.Th('Request Type'),
                html.Th('Total Requests'),
                html.Th('Mean Requests per Hour'),
                html.Th('Standard Deviation'),
                html.Th('Peak Hour')
            ]))
        ]
        
        table_rows = []
        for stat in stats:
            table_rows.append(html.Tr([
                html.Td(stat['Request Type']),
                html.Td(stat['Total Requests']),
                html.Td(stat['Mean Requests per Hour']),
                html.Td(stat['Standard Deviation']),
                html.Td(stat['Peak Hour'])
            ]))
        
        table_body = [html.Tbody(table_rows)]
        
        return html.Table(table_header + table_body, className='responsive-table')
    else:
        return html.Div("No data available for the selected filters.")

# Reset filters callback
@app.callback(
    [Output('continent-filter', 'value'),
    Output('country-filter', 'value'),
    Output('age-group-filter', 'value'),
    Output('request-type-filter', 'value'),
    Output('date-range', 'start_date'),
    Output('date-range', 'end_date')],
    [Input('reset-filters', 'n_clicks')]
)
def reset_filters(n_clicks):
    if n_clicks:
        # Ensure timestamp is datetime before calling .date()
        min_date = df['timestamp'].min().date() if pd.api.types.is_datetime64_any_dtype(df['timestamp']) else pd.to_datetime(df['timestamp'].min()).date()
        max_date = df['timestamp'].max().date() if pd.api.types.is_datetime64_any_dtype(df['timestamp']) else pd.to_datetime(df['timestamp'].max()).date()
        return [], [], [], [], min_date, max_date
    # Return the current values on initial load
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

# Navigation callbacks
@app.callback(
    [Output('current-page', 'data'),
    Output('nav-home', 'className'),
    Output('nav-map', 'className'),
    Output('nav-time', 'className'),
    Output('nav-requests', 'className'),
    Output('nav-data', 'className')],
    [Input('nav-home', 'n_clicks'),
    Input('nav-map', 'n_clicks'),
    Input('nav-time', 'n_clicks'),
    Input('nav-requests', 'n_clicks'),
    Input('nav-data', 'n_clicks')],
    [State('current-page', 'data')]
)
def update_navigation(home_clicks, map_clicks, time_clicks, requests_clicks, data_clicks, current):
    ctx = dash.callback_context
    
    # Default styles
    styles = {
        'nav-home': 'nav-link',
        'nav-map': 'nav-link',
        'nav-time': 'nav-link',
        'nav-requests': 'nav-link',
        'nav-data': 'nav-link'
    }
    
    if not ctx.triggered:
        # No clicks yet, set home as active
        styles['nav-home'] = 'nav-link active'
        return current, styles['nav-home'], styles['nav-map'], styles['nav-time'], styles['nav-requests'], styles['nav-data']
    else:
        # Get the id of the component that triggered the callback
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Set the active style for the clicked button
        styles[button_id] = 'nav-link active'
        
        # Map button_id to page name
        page_mapping = {
            'nav-home': 'home',
            'nav-map': 'map',
            'nav-time': 'time',
            'nav-requests': 'requests',
            'nav-data': 'data'
        }
        
        return page_mapping[button_id], styles['nav-home'], styles['nav-map'], styles['nav-time'], styles['nav-requests'], styles['nav-data']

@app.callback(
    Output('dashboard-content', 'children'),
    [Input('current-page', 'data')]
)
def render_content(page):
    if page == 'home':
        return [
            # Key metrics
            html.Div([
                html.Div([
                    html.H4('Total Requests', style={'color': 'white'}),
                    html.H2(id='total-requests', children='10,000', style={'color': 'white'}),
                ], className='metric-card', style={'backgroundColor': '#e74c3c'}),
                
                html.Div([
                    html.H4('Demo Requests', style={'color': 'white'}),
                    html.H2(id='demo-requests', children='2,489', style={'color': 'white'}),
                ], className='metric-card', style={'backgroundColor': '#2ecc71'}),
                
                html.Div([
                    html.H4('Job Placements', style={'color': 'white'}),
                    html.H2(id='job-placements', children='2,441', style={'color': 'white'}),
                ], className='metric-card', style={'backgroundColor': '#3498db'}),
                
                html.Div([
                    html.H4('AI Assistant Requests', style={'color': '#2c3e50'}),
                    html.H2(id='ai-assistant-requests', children='2,506', style={'color': '#2c3e50'}),
                ], className='metric-card', style={'backgroundColor': '#FFA500'})
            ], className='metrics-container'),
            
            # Charts
            html.Div([
                html.Div([
                    html.H3('Request Volume Over Time'),
                    dcc.Graph(id='time-series-chart', config={'displayModeBar': False})
                ], className='chart-container'),
                
                html.Div([
                    html.H3('Request Type Distribution'),
                    dcc.Graph(id='request-type-pie', config={'displayModeBar': False})
                ], className='chart-container'),
                
                html.Div([
                    html.H3('Requests by Country'),
                    dcc.Graph(id='country-bar-chart', config={'displayModeBar': False})
                ], className='chart-container'),
                
                html.Div([
                    html.H3('Requests by Age Group'),
                    dcc.Graph(id='age-group-chart', config={'displayModeBar': False})
                ], className='chart-container'),
            ], className='charts-grid'),
            
            # Statistics section
            html.Div([
                html.H3('Request Statistics'),
                html.Div(id='statistics-table', className='stats-table')
            ], className='statistics-section')
        ]
    elif page == 'map':
        return [
            html.H2("Geographic Distribution", className='page-title'),
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("Filter by Request Type:", style={'marginBottom': '10px', 'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='map-request-type-filter',
                            options=[{'label': req, 'value': req} for req in sorted(df['request_type'].unique())],
                            value=None,
                            placeholder='Select request type...',
                            className='filter-dropdown'
                        )
                    ], style={'marginBottom': '20px'}),
                    
                    html.H3("Requests by Country", style={'marginTop': '20px', 'marginBottom': '10px'}),
                    dcc.Graph(
                        id='world-map-chart',
                        config={'displayModeBar': True, 'scrollZoom': True}
                    )
                ], className='chart-container full-width')
            ], className='charts-grid')
        ]
    elif page == 'time':
        return [
            html.H2("Time Analysis", className='page-title'),
            html.Div([
                html.Div([
                    html.H3("Hourly Distribution"),
                    dcc.Graph(
                        id='hourly-chart',
                        config={'displayModeBar': False}
                    )
                ], className='chart-container'),
                
                html.Div([
                    html.H3("Daily Distribution"),
                    dcc.Graph(
                        id='daily-chart',
                        config={'displayModeBar': False}
                    )
                ], className='chart-container'),
                
                html.Div([
                    html.H3("Monthly Distribution"),
                    dcc.Graph(
                        id='monthly-chart',
                        config={'displayModeBar': False}
                    )
                ], className='chart-container full-width')
            ], className='charts-grid')
        ]
    elif page == 'requests':
        return [
            html.H2("Request Type Analysis", className='page-title'),
            html.Div([
                html.Div([
                    html.H3("Request Type Distribution"),
                    dcc.Graph(
                        id='request-type-pie-detailed',
                        config={'displayModeBar': False}
                    )
                ], className='chart-container'),
                
                html.Div([
                    html.H3("Request Types Over Time"),
                    dcc.Graph(
                        id='request-time-series',
                        config={'displayModeBar': False}
                    )
                ], className='chart-container'),
                
                html.Div([
                    html.H3("Request Types by Country"),
                    dcc.Graph(
                        id='request-country-heatmap',
                        config={'displayModeBar': False}
                    )
                ], className='chart-container full-width')
            ], className='charts-grid')
        ]
    elif page == 'data':
        return [
            html.H2("Raw Data", className='page-title'),
            html.Div([
                html.Div([
                    html.H3("Data Table"),
                    html.Div([
                        html.Div([
                            html.Button("Export CSV", id="export-csv", className="btn-primary", style={"marginRight": "10px"}),
                            html.Button("Export JSON", id="export-json", className="btn-primary", style={"marginRight": "10px"}),
                            html.Button("Export Excel", id="export-excel", className="btn-primary"),
                            html.Div(id="export-message", style={"marginTop": "10px", "color": "green"})
                        ], style={"marginBottom": "20px", "display": "flex", "flexWrap": "wrap", "gap": "10px"}),
                        html.Div([
                            html.Label("Export Options:", style={"fontWeight": "bold", "marginRight": "10px"}),
                            dcc.RadioItems(
                                id='export-option',
                                options=[
                                    {'label': 'Current View', 'value': 'current'},
                                    {'label': 'All Filtered Data', 'value': 'all'}
                                ],
                                value='current',
                                labelStyle={'display': 'inline-block', 'marginRight': '20px'}
                            )
                        ], style={"marginBottom": "20px"})
                    ]),
                    dash.dash_table.DataTable(
                        id='data-table',
                        columns=[{"name": i, "id": i} for i in df.columns],
                        data=df.head(100).to_dict('records'),
                        page_size=20,
                        filter_action="native",
                        sort_action="native",
                        sort_mode="multi",
                        style_table={'overflowX': 'auto', 'height': '500px'},
                        style_cell={
                            'height': 'auto',
                            'minWidth': '100px', 'width': '150px', 'maxWidth': '200px',
                            'whiteSpace': 'normal',
                            'textAlign': 'left'
                        },
                        style_header={
                            'backgroundColor': 'rgb(230, 230, 230)',
                            'fontWeight': 'bold'
                        },
                        export_format="csv"
                    )
                ], className='chart-container full-width')
            ], className='charts-grid')
        ]

# Add a new callback for the map page to update the map based on filters
# Add this after the other callbacks:

@app.callback(
    Output('world-map-chart', 'figure'),
    [Input('map-request-type-filter', 'value'),
    Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_world_map(map_request_type, continents, countries, age_groups, request_types, start_date, end_date):
    # Use the filter_dataframe function to apply all filters consistently
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Apply the map-specific request type filter if selected
    if map_request_type:
        filtered_df = filtered_df[filtered_df['request_type'] == map_request_type]
    
    # Group by country and count
    country_counts = filtered_df.groupby('country').size().reset_index(name='count')
    
    # Create a choropleth map
    fig = px.choropleth(
        country_counts,
        locations='country',
        locationmode='country names',
        color='count',
        hover_name='country',
        hover_data={'count': True},
        color_continuous_scale='Viridis',
        labels={'count': 'Number of Requests'},
        title=f'Request Distribution by Country{" - " + map_request_type if map_request_type else ""}'
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0),
        coloraxis_colorbar=dict(
            title='Number of Requests',
            x=0.9
        ),
        height=600,  # Increased height for better visibility
        geo=dict(
            showframe=True,
            showcoastlines=True,
            projection_type='natural earth',
            showcountries=True,
            countrycolor='rgba(0, 0, 0, 0.5)',
            coastlinecolor='rgba(0, 0, 0, 0.5)',
            landcolor='rgba(230, 230, 230, 0.5)'
        ),
        title=dict(
            font=dict(size=18)
        )
    )
    
    return fig

# Update the hourly chart callback to respond to all filters
@app.callback(
    Output('hourly-chart', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_hourly_chart(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Group by hour and count
    hourly_counts = filtered_df.groupby('hour').size().reset_index(name='count')
    
    # Create the figure
    fig = px.bar(
        hourly_counts,
        x='hour',
        y='count',
        labels={'hour': 'Hour of Day', 'count': 'Number of Requests'},
        title='Requests by Hour of Day',
        color_discrete_sequence=['#3498db']  # Use blue color to match screenshot
    )
    
    fig.update_layout(
        xaxis=dict(tickmode='linear', tick0=0, dtick=1),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=300  # Set consistent height
    )
    
    return fig

# Update the daily chart callback to respond to all filters
@app.callback(
    Output('daily-chart', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_daily_chart(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Define the order of days
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Group by day and count
    daily_counts = filtered_df['day'].value_counts().reset_index()
    daily_counts.columns = ['day', 'count']
    
    # Sort by the defined order
    daily_counts['day'] = pd.Categorical(daily_counts['day'], categories=day_order, ordered=True)
    daily_counts = daily_counts.sort_values('day')
    
    # Create the figure
    fig = px.bar(
        daily_counts,
        x='day',
        y='count',
        labels={'day': 'Day of Week', 'count': 'Number of Requests'},
        title='Requests by Day of Week',
        color='count',
        color_continuous_scale='Teal'
    )
    
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        coloraxis_showscale=False,
        height=300  # Set consistent height
    )
    
    return fig

# Update the monthly chart callback to respond to all filters
@app.callback(
    Output('monthly-chart', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_monthly_chart(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Define the order of months
    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                'July', 'August', 'September', 'October', 'November', 'December']
    
    # Group by month and count
    monthly_counts = filtered_df['month'].value_counts().reset_index()
    monthly_counts.columns = ['month', 'count']
    
    # Sort by the defined order
    monthly_counts['month'] = pd.Categorical(monthly_counts['month'], categories=month_order, ordered=True)
    monthly_counts = monthly_counts.sort_values('month')
    
    # Create the figure
    fig = px.line(
        monthly_counts,
        x='month',
        y='count',
        labels={'month': 'Month', 'count': 'Number of Requests'},
        title='Requests by Month',
        markers=True
    )
    
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=300  # Set consistent height
    )
    
    return fig

# Add these after the other callbacks:

@app.callback(
    Output('request-type-pie-detailed', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_request_type_pie_detailed(continents, countries, age_groups, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, [], start_date, end_date)
    
    # Group by request type and count
    request_type_counts = filtered_df['request_type'].value_counts().reset_index()
    request_type_counts.columns = ['request_type', 'count']
    
    # Create the figure
    fig = px.pie(
        request_type_counts, 
        values='count', 
        names='request_type',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3,
        title='Request Type Distribution'
    )
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=300  # Set consistent height
    )
    
    fig.update_traces(textinfo='percent+label')
    
    return fig

@app.callback(
    Output('request-time-series', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_request_time_series(continents, countries, age_groups, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, [], start_date, end_date)
    
    # Group by date and request type
    request_time = filtered_df.groupby([filtered_df['timestamp'].dt.date, 'request_type']).size().reset_index(name='count')
    
    # Create the figure
    fig = px.line(
        request_time,
        x='timestamp',
        y='count',
        color='request_type',
        title='Request Types Over Time',
        labels={'timestamp': 'Date', 'count': 'Number of Requests', 'request_type': 'Request Type'}
    )
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
        height=300,  # Set consistent height
        xaxis=dict(
            title='Date',
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            title='Number of Requests',
            gridcolor='lightgray',
            showgrid=True
        )
    )
    
    return fig

@app.callback(
    Output('request-country-heatmap', 'figure'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
@handle_error
def update_request_country_heatmap(continents, countries, age_groups, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, [], start_date, end_date)
    
    # Group by country and request type
    country_request = filtered_df.groupby(['country', 'request_type']).size().reset_index(name='count')
    
    # Pivot the data for the heatmap
    heatmap_data = country_request.pivot(index='country', columns='request_type', values='count').fillna(0)
    
    # Take top 10 countries by total requests
    top_countries = filtered_df['country'].value_counts().nlargest(10).index.tolist()
    heatmap_data = heatmap_data.loc[heatmap_data.index.isin(top_countries)]
    
    # Create the figure
    fig = px.imshow(
        heatmap_data,
        labels=dict(x='Request Type', y='Country', color='Number of Requests'),
        title='Request Types by Country (Top 10 Countries)',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=300  # Set consistent height
    )
    
    return fig

# Add callback for the data table
@app.callback(
    Output('data-table', 'data'),
    [Input('continent-filter', 'value'),
    Input('country-filter', 'value'),
    Input('age-group-filter', 'value'),
    Input('request-type-filter', 'value'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date')]
)
def update_data_table(continents, countries, age_groups, request_types, start_date, end_date):
    filtered_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    return filtered_df.head(100).to_dict('records')

# Add download callbacks for different formats
@app.callback(
    Output('export-message', 'children'),
    [Input('export-csv', 'n_clicks'),
    Input('export-json', 'n_clicks'),
    Input('export-excel', 'n_clicks')],
    [State('export-option', 'value'),
    State('continent-filter', 'value'),
    State('country-filter', 'value'),
    State('age-group-filter', 'value'),
    State('request-type-filter', 'value'),
    State('date-range', 'start_date'),
    State('date-range', 'end_date'),
    State('data-table', 'derived_virtual_data')],
    prevent_initial_call=True
)
def export_data(csv_clicks, json_clicks, excel_clicks, export_option, 
            continents, countries, age_groups, request_types, start_date, end_date,
            table_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Get the appropriate data based on the export option
    if export_option == 'current':
        # Use the current table view (with any applied filters)
        if table_data is None:
            return "No data to export"
        export_df = pd.DataFrame(table_data)
    else:
        # Use all filtered data
        export_df = filter_dataframe(df, continents, countries, age_groups, request_types, start_date, end_date)
    
    # Create a timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if button_id == 'export-csv':
            export_df.to_csv(f'dashboard_export_{timestamp}.csv', index=False)
            return f"Data exported to CSV successfully: dashboard_export_{timestamp}.csv"
        
        elif button_id == 'export-json':
            export_df.to_json(f'dashboard_export_{timestamp}.json', orient='records')
            return f"Data exported to JSON successfully: dashboard_export_{timestamp}.json"
        
        elif button_id == 'export-excel':
            export_df.to_excel(f'dashboard_export_{timestamp}.xlsx', index=False)
            return f"Data exported to Excel successfully: dashboard_export_{timestamp}.xlsx"
        
    except Exception as e:
        return f"Error exporting data: {str(e)}"
    
    return ""

# Run the app
if __name__ == '__main__':
    app.run(debug=True)  # Updated from app.run_server(debug=True)
