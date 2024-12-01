// src/redux/store.js
import { configureStore } from '@reduxjs/toolkit';
import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import { combineReducers } from 'redux';
import consultationReducer from './slices/consultationSlice';
import userReducer from './slices/userSlice';

const rootReducer = combineReducers({
  consultation: consultationReducer,
  user: userReducer
});

const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['user'] // We'll persist user data but not consultation state
};

const persistedReducer = persistReducer(persistConfig, rootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST', 'persist/REHYDRATE']
      }
    })
});

export const persistor = persistStore(store);