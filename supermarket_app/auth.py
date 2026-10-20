"""Session-based access gate for the single-account local prototype.

The default password is stored as a salted PBKDF2 hash. Authentication state
belongs to the current Streamlit session; it is not persisted in the browser.
"""
import hashlib
import hmac
import os
from pathlib import Path

import streamlit as st

# Deployment credentials are supplied through the hosting platform's secrets.
USERNAME = os.environ.get('APP_USERNAME', '')
PASSWORD_ITERATIONS = 600000
try:
    PASSWORD_SALT = bytes.fromhex(os.environ.get('APP_PASSWORD_SALT', ''))
    PASSWORD_HASH = os.environ.get('APP_PASSWORD_HASH', '')
    if not USERNAME or len(PASSWORD_SALT) < 16 or len(bytes.fromhex(PASSWORD_HASH)) != 32:
        raise ValueError('Missing or invalid authentication settings')
except ValueError:
    st.error('Staff sign-in is not configured. Contact the administrator.')
    st.stop()


def credentials_valid(username, password):
    """Compare derived hashes, including when the username is incorrect."""
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                   PASSWORD_SALT, PASSWORD_ITERATIONS).hex()
    correct_password = hmac.compare_digest(candidate, PASSWORD_HASH)
    correct_username = hmac.compare_digest(username.encode('utf-8'), USERNAME.encode('utf-8'))
    return correct_username and correct_password


def sign_in():
    """A widget callback runs before the next page render."""
    username = st.session_state.get('login_username', '')
    password = st.session_state.get('login_password', '')
    valid = credentials_valid(username, password)
    # Never retain the submitted password after processing the form.
    st.session_state['login_password'] = ''
    if valid:
        st.session_state.clear()
        st.session_state['authenticated_user'] = USERNAME
    else:
        st.session_state['login_error'] = 'Incorrect username or password. Please try again.'


def sign_out():
    """Clear access, navigation and unsaved forms before rendering the login page."""
    st.session_state.clear()


def require_login():
    """Stop execution before protected widgets or database queries are reached."""
    if st.session_state.get('authenticated_user') == USERNAME:
        return
    hero, form_column = st.columns([1.15, 1], gap='large', vertical_alignment='center')
    with hero:
        st.markdown('<div class="login-eyebrow">SUPERMARKET OPERATIONS</div>', unsafe_allow_html=True)
        st.markdown('<h1 class="login-headline">A fresh start.<br>A well-stocked store.</h1>', unsafe_allow_html=True)
        st.markdown('<p class="login-description">Your everyday workspace for purchasing, deliveries and inventory.</p>', unsafe_allow_html=True)
        st.image(str(Path(__file__).with_name('assets') / 'login_market.svg'), width='stretch')
        st.markdown('<div class="login-features"><span>Inventory</span><span>Purchase orders</span><span>Goods receiving</span></div>', unsafe_allow_html=True)
    with form_column:
        with st.container(border=True):
            st.subheader('Welcome back')
            st.caption('Sign in to your staff workspace to continue.')
            with st.form('login_form'):
                st.text_input('Username', key='login_username', placeholder='Enter your username', max_chars=100)
                st.text_input('Password', key='login_password', type='password', placeholder='Enter your password', max_chars=256)
                st.form_submit_button('Sign in', key='login_submit', type='primary',
                                      on_click=sign_in, width='stretch')
            if st.session_state.get('login_error'):
                st.error(st.session_state['login_error'])
            st.caption('Staff access only. Contact your project administrator if you need help signing in.')
    st.stop()
