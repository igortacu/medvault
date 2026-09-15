import App from '../App.tsx';
import Documents from '../features/documents/Documents.tsx';
import Diagnostics from '../features/documents/diagnostics/Diagnostics.tsx';
import Prescriptions from '../features/documents/prescriptions/Prescriptions.tsx';
import Certificates from '../features/documents/certificates/Certificates.tsx';
import MedicalInfo from '../features/documents/otherMedications/MedicalInfo.tsx';
import Recipients from '../features/Recipients/Recipients.tsx';
import Profile from '../features/profile/Profile.tsx';
import { createBrowserRouter } from 'react-router-dom';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        path: 'documents',
        element: <Documents />,
        children: [
          {
            index: true,
            element: <Diagnostics />,
          },
          {
            path: 'prescriptions',
            element: <Prescriptions />,
          },
          {
            path: 'certificates',
            element: <Certificates />,
          },
          {
            path: 'other_medications',
            element: <MedicalInfo />,
          },
        ],
      },
      {
        path: 'profile',
        element: <Profile />,
      },
      {
        path: 'recipients',
        element: <Recipients />,
      },
    ],
  },
]);
