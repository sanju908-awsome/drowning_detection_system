import { FirebaseApp, getApp, getApps, initializeApp } from 'firebase/app'
import { Auth, getAuth } from 'firebase/auth'

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const firebaseConfigured = Object.values(config).every(value => typeof value === 'string' && value.length > 0)
let firebaseApp: FirebaseApp | null = null
let firebaseAuth: Auth | null = null
if (firebaseConfigured) {
  firebaseApp = getApps().length ? getApp() : initializeApp(config)
  firebaseAuth = getAuth(firebaseApp)
}
export const auth = firebaseAuth
