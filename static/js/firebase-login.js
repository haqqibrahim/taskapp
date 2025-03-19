import { initializeApp } from "https://www.gstatic.com/firebasejs/9.22.2/firebase-app.js";
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/9.22.2/firebase-auth.js";

// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
    apiKey: "AIzaSyC0rOlwzIq50zhe4I0WBnZ5CbRJuOWxT-M",
    authDomain: "f1-app-d2ac7.firebaseapp.com",
    projectId: "f1-app-d2ac7",
    storageBucket: "f1-app-d2ac7.firebasestorage.app",
    messagingSenderId: "627228577249",
    appId: "1:627228577249:web:9713d03a1b7f187d7016a0",
    measurementId: "G-XT3TQ3RBQD"
  };

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Function to update UI based on authentication status
function updateUI(user) {
    const loginBox = document.getElementById("login-box");
    const logoutBtn = document.getElementById("logout-btn");
    const authIndicator = document.getElementById("auth-indicator");

    if (user) {
        document.cookie = `token=${user.accessToken}; path=/; SameSite=Strict`;
        if (authIndicator) authIndicator.textContent = `Logged in as ${user.email}`;
        if (loginBox) loginBox.style.display = "none";
        if (logoutBtn) logoutBtn.style.display = "block";
    } else {
        document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
        if (authIndicator) authIndicator.textContent = "Not logged in";
        if (loginBox) loginBox.style.display = "block";
        if (logoutBtn) logoutBtn.style.display = "none";
    }
}

// Handle Authentication State Changes
onAuthStateChanged(auth, (user) => {
    updateUI(user);
});

// Handle Signup
export function signup() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    createUserWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            updateUI(userCredential.user);
            window.location.href = "/dashboard";
        })
        .catch((error) => {
            console.error("Signup Error:", error);
            alert(error.message);
        });
}

// Handle Login
export function login() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    signInWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            updateUI(userCredential.user);
            window.location.href = "/dashboard";
        })
        .catch((error) => {
            console.error("Login Error:", error);
            alert(error.message);
        });
}

// Handle Logout
export function logout() {
    const auth = getAuth();
    signOut(auth)
        .then(() => {
            document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
            window.location.href = "/";
        })
        .catch((error) => {
            console.error("Logout Error:", error);
        });
}
