// src/redux/slices/userSlice.js
import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  firstName: null,
  lastName: null,
  email: null,
  consultations: []
};

const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    setUserInfo: (state, action) => {
      const { firstName, lastName, email } = action.payload;
      state.firstName = firstName || '';
      state.lastName = lastName || '';
      state.email = email || '';
    },
    addConsultation: (state, action) => {
      state.consultations.push(action.payload);
    },
    clearUser: (state) => {
      return initialState;
    }
  }
});

export const { setUserInfo, addConsultation, clearUser } = userSlice.actions;

export default userSlice.reducer;