import App from '../App.tsx';
import Documents from '../features/documents/Documents.tsx';
import Diagnostics from '../features/documents/diagnostics/Diagnostics.tsx';
import Prescriptions from '../features/documents/prescriptions/Prescriptions.tsx';
import Certificates from '../features/documents/certificates/Certificates.tsx';
import MedicalInfo from '../features/documents/otherMedications/MedicalInfo.tsx';
import Recipients from '../features/Recipients/Recipients.tsx';
import Profile from '../features/profile/Profile.tsx';
import { createBrowserRouter } from 'react-router-dom';
import Institutions from '../features/institutions/Institutions.tsx';
import CaregiverDetail from '../features/caregiver/CaregiverDetail.tsx';
import { RecipientGate } from '../features/Recipients/RecipientGate.tsx';

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
            element: (
              <RecipientGate tab="diagnostics">
                <Diagnostics />
              </RecipientGate>
            ),
          },
          {
            path: 'prescriptions',
            element: (
              <RecipientGate tab="prescriptions">
                <Prescriptions />
              </RecipientGate>
            ),
          },
          {
            path: 'certificates',
            element: (
              <RecipientGate tab="certificates">
                <Certificates />
              </RecipientGate>
            ),
          },
          {
            path: 'other_medications',
            element: (
              <RecipientGate tab="otherMedicalInfo">
                <MedicalInfo />
              </RecipientGate>
            ),
          },
        ],
      },
      {
        path: 'profile',
        element: <Profile />,
      },
      {
        path: 'caregiver',
        element: (
          <RecipientGate ownOnly>
            <CaregiverDetail />
          </RecipientGate>
        ),
      },
      {
        path: 'recipients',
        element: <Recipients />,
      },
      {
        path: 'institutions',
        element: (
          <RecipientGate ownOnly>
            <Institutions />
          </RecipientGate>
        ),
      },
    ],
  },
]);
