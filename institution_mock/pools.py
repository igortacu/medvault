"""Fixed value pools for the fixture generator (Epic 6, data generator).

Four pools from the task breakdown: LOINC lab codes, medications, admission
reasons and document types, plus the supporting outpatient diagnoses and
specialties. Human-readable text is Romanian; codes stay in their systems
(LOINC, CIM-10 / ICD-10, ATC, urn:medvault:document-type). See RESEARCH.md for
where the document structure comes from.
"""
from __future__ import annotations

LOINC = "http://loinc.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10"
ATC = "http://www.whocc.no/atc"
UCUM = "http://unitsofmeasure.org"

# --- Pool 1: LOINC lab parameters -----------------------------------------------
# code -> (Romanian name, English LOINC display, unit, low, high, decimals)
LAB_TESTS: dict[str, tuple[str, str, str, float, float, int]] = {
    # Hemoleucogramă
    "718-7": ("Hemoglobină", "Hemoglobin [Mass/volume] in Blood", "g/dL", 12.0, 16.0, 1),
    "6690-2": ("Leucocite", "Leukocytes [#/volume] in Blood", "10*9/L", 4.0, 9.0, 1),
    "789-8": ("Eritrocite", "Erythrocytes [#/volume] in Blood", "10*12/L", 3.8, 5.2, 2),
    "777-3": ("Trombocite", "Platelets [#/volume] in Blood", "10*9/L", 150, 400, 0),
    "4544-3": ("Hematocrit", "Hematocrit [Volume Fraction] of Blood", "%", 36.0, 48.0, 1),
    "30341-2": ("VSH", "Erythrocyte sedimentation rate", "mm/h", 2, 20, 0),
    # Examen biochimic
    "15074-8": ("Glucoză", "Glucose [Moles/volume] in Blood", "mmol/L", 3.9, 6.1, 1),
    "14682-9": ("Creatinină", "Creatinine [Moles/volume] in Serum or Plasma", "umol/L", 53, 106, 0),
    "22664-7": ("Uree", "Urea [Moles/volume] in Serum or Plasma", "mmol/L", 2.5, 8.3, 1),
    "14647-2": ("Colesterol total", "Cholesterol [Moles/volume] in Serum or Plasma", "mmol/L", 3.0, 5.2, 2),
    "1742-6": ("ALT", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "U/L", 7, 40, 0),
    "1920-8": ("AST", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "U/L", 10, 40, 0),
    "6298-4": ("Potasiu", "Potassium [Moles/volume] in Blood", "mmol/L", 3.5, 5.1, 1),
    "2951-2": ("Sodiu", "Sodium [Moles/volume] in Serum or Plasma", "mmol/L", 136, 145, 0),
    "4548-4": ("Hemoglobină glicată (HbA1c)", "Hemoglobin A1c/Hemoglobin.total in Blood", "%", 4.0, 6.0, 1),
    "10839-9": ("Troponina I", "Troponin I.cardiac [Mass/volume] in Serum or Plasma", "ng/mL", 0.0, 0.04, 2),
    # Profil tiroidian
    "3016-3": ("TSH", "Thyrotropin [Units/volume] in Serum or Plasma", "mIU/L", 0.4, 4.0, 2),
    "14920-3": ("T4 liber", "Thyroxine (T4) free [Moles/volume] in Serum or Plasma", "pmol/L", 10.0, 22.0, 1),
    "8099-4": ("Anticorpi anti-TPO", "Thyroperoxidase Ab [Units/volume] in Serum or Plasma", "[IU]/mL", 0, 34, 0),
    # Hemostază
    "6301-6": ("INR", "INR in Platelet poor plasma by Coagulation assay", "{INR}", 0.8, 1.2, 2),
    "3173-2": ("aPTT", "aPTT in Blood by Coagulation assay", "s", 25, 37, 0),
    # Examenul sumar al urinei
    "5811-5": ("Densitate relativă", "Specific gravity of Urine by Test strip", "1", 1.005, 1.030, 3),
    "5803-2": ("pH", "pH of Urine by Test strip", "[pH]", 5.0, 7.0, 1),
    "2888-6": ("Proteine", "Protein [Mass/volume] in Urine", "g/L", 0.0, 0.14, 2),
    "5821-4": ("Leucocite (sediment)", "Leukocytes [#/area] in Urine sediment by Microscopy high power field", "/[HPF]", 0, 5, 0),
    "13945-1": ("Eritrocite (sediment)", "Erythrocytes [#/area] in Urine sediment by Microscopy high power field", "/[HPF]", 0, 3, 0),
}

# Lab report panels: (document subtype, Romanian title, form, LOINC codes)
LAB_PANELS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("blood_test", "Hemoleucogramă completă", "Formular 2xx/e — Hemoleucograma",
     ("718-7", "6690-2", "789-8", "777-3", "4544-3", "30341-2")),
    ("biochemistry_report", "Examen biochimic al sângelui", "Formular 2xx/e — Examenul biochimic",
     ("15074-8", "14682-9", "22664-7", "14647-2", "1742-6", "1920-8", "6298-4", "2951-2")),
    ("urinalysis", "Examenul sumar al urinei", "Formular 2xx/e — Examenul sumar al urinei",
     ("5811-5", "5803-2", "2888-6", "5821-4", "13945-1")),
    ("hormone_test", "Profil hormonal tiroidian", "Formular 2xx/e — Examenul la hormoni",
     ("3016-3", "14920-3", "8099-4")),
    ("blood_test", "Coagulogramă (hemostază)", "Formular 2xx/e — Examenul sistemului de hemostază",
     ("6301-6", "3173-2", "777-3")),
)

VITALS = {
    "29463-7": ("Greutate corporală", "Body weight", "kg"),
    "8302-2": ("Talie", "Body height", "cm"),
    "8480-6": ("Tensiune arterială sistolică", "Systolic blood pressure", "mm[Hg]"),
    "8462-4": ("Tensiune arterială diastolică", "Diastolic blood pressure", "mm[Hg]"),
}

# --- Pool 2: medications -----------------------------------------------------------
# key -> (DCI, Romanian form/strength, commercial name, ATC, dosage, CNAM-compensated)
# Commercial names are ones plausibly on the Moldovan market; the compensated flag is
# synthetic and does not reflect the current CNAM list.
MEDICATIONS: dict[str, tuple[str, str, str, str, str, bool]] = {
    "amlodipine": ("Amlodipinum", "comprimate 5 mg", "Normodipine", "C08CA01", "1 comprimat dimineața", True),
    "enalapril": ("Enalaprilum", "comprimate 10 mg", "Enap", "C09AA02", "1 comprimat de 2 ori pe zi", True),
    "lisinopril": ("Lisinoprilum", "comprimate 10 mg", "Diroton", "C09AA03", "1 comprimat dimineața", True),
    "bisoprolol": ("Bisoprololum", "comprimate 5 mg", "Concor", "C07AB07", "1 comprimat dimineața", True),
    "atorvastatin": ("Atorvastatinum", "comprimate 20 mg", "Atoris", "C10AA05", "1 comprimat seara", True),
    "metformin": ("Metforminum", "comprimate 850 mg", "Siofor", "A10BA02", "1 comprimat de 2 ori pe zi, după masă", True),
    "insulin_glargine": ("Insulinum glarginum", "soluție injectabilă 100 UI/ml", "Lantus SoloStar", "A10AE04", "18 UI subcutanat seara", True),
    "furosemide": ("Furosemidum", "comprimate 40 mg", "Furosemid", "C03CA01", "1 comprimat dimineața, pe stomacul gol", True),
    "apixaban": ("Apixabanum", "comprimate 5 mg", "Eliquis", "B01AF02", "1 comprimat de 2 ori pe zi", False),
    "aspirin": ("Acidum acetylsalicylicum", "comprimate 75 mg", "Aspirin Cardio", "B01AC06", "1 comprimat la prânz", False),
    "levothyroxine": ("Levothyroxinum natricum", "comprimate 50 mcg", "Eutirox", "H03AA01", "1 comprimat dimineața, cu 30 min înainte de masă", True),
    "salbutamol": ("Salbutamolum", "aerosol 100 mcg/doză", "Ventolin", "R03AC02", "1–2 inhalații la nevoie", True),
    "omeprazole": ("Omeprazolum", "capsule 20 mg", "Omez", "A02BC01", "1 capsulă dimineața, înainte de masă", False),
    "amoxiclav": ("Amoxicillinum + Acidum clavulanicum", "comprimate 875/125 mg", "Amoksiklav", "J01CR02", "1 comprimat la 12 ore, 7 zile", False),
    "paracetamol": ("Paracetamolum", "comprimate 500 mg", "Paracetamol", "N02BE01", "1 comprimat la nevoie, maximum 4 pe zi", False),
    "ibuprofen": ("Ibuprofenum", "comprimate 400 mg", "Nurofen", "M01AE01", "1 comprimat de 3 ori pe zi, după masă, 5 zile", False),
    "ferrous_sulfate": ("Ferrosi sulfas", "comprimate 320 mg", "Sorbifer Durules", "B03AA07", "1 comprimat de 2 ori pe zi", False),
    "folic_acid": ("Acidum folicum", "comprimate 400 mcg", "Acid folic", "B03BB01", "1 comprimat pe zi", False),
    "cholecalciferol": ("Colecalciferolum", "soluție orală 15000 UI/ml", "Aquadetrim", "A11CC05", "1 picătură pe zi", False),
    "ceftriaxone": ("Ceftriaxonum", "pulbere pentru soluție injectabilă 1 g", "Ceftriaxon", "J01DD04", "1 g intravenos o dată pe zi", False),
}

# --- Pool 3: admission reasons (inpatient, CIM-10) -----------------------------------
# key -> (CIM-10 code, Romanian diagnosis, ward, specialty)
ADMISSION_REASONS: dict[str, tuple[str, str, str, str]] = {
    "unstable_angina": ("I20.0", "Angină pectorală instabilă", "Secția cardiologie", "Cardiologie"),
    "paroxysmal_af": ("I48.0", "Fibrilație atrială paroxistică", "Secția cardiologie", "Cardiologie"),
    "heart_failure": ("I50.0", "Insuficiență cardiacă congestivă", "Secția cardiologie", "Cardiologie"),
    "pneumonia": ("J18.9", "Pneumonie, neprecizată", "Secția pneumologie", "Pneumologie"),
    "copd_exacerbation": ("J44.1", "Bronhopneumopatie cronică obstructivă cu exacerbare acută", "Secția pneumologie", "Pneumologie"),
    "acute_cholecystitis": ("K81.0", "Colecistită acută", "Secția chirurgie generală", "Chirurgie generală"),
    "pyelonephritis": ("N10", "Nefrită tubulo-interstițială acută (pielonefrită acută)", "Secția nefrologie", "Nefrologie"),
    "femoral_neck_fracture": ("S72.0", "Fractură de col femural", "Secția ortopedie și traumatologie", "Ortopedie și traumatologie"),
    "ischaemic_stroke": ("I63.9", "Infarct cerebral, neprecizat", "Secția neurologie", "Neurologie"),
}

# Outpatient diagnoses: key -> (CIM-10 code, Romanian name, specialty)
DIAGNOSES: dict[str, tuple[str, str, str]] = {
    "hypertension": ("I10", "Hipertensiune arterială esențială (primară)", "Cardiologie"),
    "diabetes2": ("E11.9", "Diabet zaharat tip 2 fără complicații", "Endocrinologie"),
    "hypercholesterolaemia": ("E78.0", "Hipercolesterolemie pură", "Cardiologie"),
    "af": ("I48.0", "Fibrilație atrială paroxistică", "Cardiologie"),
    "hypothyroidism": ("E03.9", "Hipotiroidie, neprecizată", "Endocrinologie"),
    "iron_anaemia": ("D50.9", "Anemie feriprivă, neprecizată", "Medicină internă"),
    "gastritis": ("K29.5", "Gastrită cronică, neprecizată", "Gastroenterologie"),
    "low_back_pain": ("M54.5", "Lombalgie", "Neurologie"),
    "knee_arthrosis": ("M17.9", "Gonartroză, neprecizată", "Ortopedie și traumatologie"),
    "asthma": ("J45.9", "Astm bronșic, neprecizat", "Pneumologie"),
    "uri": ("J06.9", "Infecție acută a căilor respiratorii superioare, neprecizată", "Medicină de familie"),
    "bronchitis": ("J20.9", "Bronșită acută, neprecizată", "Pediatrie"),
    "pregnancy": ("Z34.0", "Supravegherea primei sarcini normale", "Obstetrică-ginecologie"),
    "general_exam": ("Z00.0", "Examen medical general", "Medicină de familie"),
    "child_exam": ("Z00.1", "Examen de rutină al sănătății copilului", "Pediatrie"),
    "exam_education": ("Z02.0", "Examen pentru admitere într-o instituție de învățământ", "Medicină de familie"),
    "exam_employment": ("Z02.1", "Examen înainte de angajare", "Medicină de familie"),
    "exam_driving": ("Z02.4", "Examen pentru permis de conducere", "Medicină de familie"),
    "exam_sport": ("Z02.5", "Examen pentru practicarea sportului", "Medicină sportivă"),
}

# --- Pool 4: document types --------------------------------------------------------------
# MedVault subtype -> (category, Romanian title, Moldovan form, FHIR resource type)
# Mirrors backend/app/documents/document_types.py (D5). birth_certificate is
# deliberately absent (D16): the mock never generates one. disability_certificate is
# issued by CNDDCM, not by a hospital, so no institution here generates it either.
DOCUMENT_TYPES: dict[str, tuple[str, str, str, str]] = {
    # diagnoses
    "diagnosis_record": ("diagnoses", "Diagnostic", "Fișa medicală 025/e", "Condition"),
    "consultation_report": ("diagnoses", "Consultația medicului specialist", "Aviz consultativ", "DocumentReference"),
    "progress_note": ("diagnoses", "Notă de evoluție", "Fișa medicală 025/e", "DocumentReference"),
    "medical_history": ("diagnoses", "Anamneza bolii", "Fișa medicală 025/e", "DocumentReference"),
    "family_history": ("diagnoses", "Anamneză familială", "Fișa medicală 025/e", "DocumentReference"),
    "surgical_history": ("diagnoses", "Antecedente chirurgicale", "Fișa medicală 025/e", "DocumentReference"),
    "medical_examination_report": ("diagnoses", "Raport de examen medical profilactic", "Fișa medicală 025/e", "DocumentReference"),
    # certificates
    "health_certificate": ("certificates", "Adeverință medicală", "Formular 086/e", "DocumentReference"),
    "medical_examination_certificate": ("certificates", "Adeverință medicală (examen la angajare)", "Formular 086/e", "DocumentReference"),
    "fitness_certificate": ("certificates", "Certificat medical al conducătorului auto", "Formular 083/e", "DocumentReference"),
    "illness_certificate": ("certificates", "Certificat de concediu medical", "Certificat digital (PCCM)", "DocumentReference"),
    "vaccination_certificate": ("certificates", "Certificat de vaccinare", "Formular 063-3/e", "DocumentReference"),
    "hospitalization_certificate": ("certificates", "Adeverință de spitalizare", "Adeverință", "DocumentReference"),
    "pregnancy_certificate": ("certificates", "Certificat de graviditate", "Adeverință", "DocumentReference"),
    # analyses
    "blood_test": ("analyses", "Hemoleucogramă", "Formular 2xx/e", "DiagnosticReport"),
    "biochemistry_report": ("analyses", "Examen biochimic", "Formular 2xx/e", "DiagnosticReport"),
    "urinalysis": ("analyses", "Examenul sumar al urinei", "Formular 2xx/e", "DiagnosticReport"),
    "hormone_test": ("analyses", "Examenul la hormoni", "Formular 2xx/e", "DiagnosticReport"),
    "microbiology_report": ("analyses", "Examen bacteriologic", "Rezultatul analizei", "DiagnosticReport"),
    "pathology_report": ("analyses", "Examen histopatologic", "Buletin histopatologic", "DiagnosticReport"),
    "xray_report": ("analyses", "Radiografie", "Protocol radiologic", "DiagnosticReport"),
    "ultrasound_report": ("analyses", "Examen ecografic", "Protocol ecografic", "DiagnosticReport"),
    "ct_report": ("analyses", "Tomografie computerizată", "Protocol imagistic", "DiagnosticReport"),
    "mri_report": ("analyses", "Rezonanță magnetică nucleară", "Protocol imagistic", "DiagnosticReport"),
    "ecg_report": ("analyses", "Electrocardiogramă", "Protocol ECG", "DiagnosticReport"),
    "endoscopy_report": ("analyses", "Examen endoscopic", "Protocol endoscopic", "DiagnosticReport"),
    "operative_report": ("analyses", "Protocol operator", "Fișa 003/e — protocolul operației", "DiagnosticReport"),
    "radiology_images": ("analyses", "Imagini radiologice", "DICOM", "ImagingStudy"),
    # prescriptions
    "prescription": ("prescriptions", "Rețetă", "Formular nr. 1 / e-Rețeta", "MedicationRequest"),
    "medication_record": ("prescriptions", "Tratament administrat", "Fișa medicală 025/e", "MedicationStatement"),
    "treatment_plan": ("prescriptions", "Plan de tratament", "Fișa medicală 025/e", "CarePlan"),
    "procedure_record": ("prescriptions", "Manipulație / procedură", "Registrul 069/e", "Procedure"),
    # other medical information
    "hospitalization_record": ("other_med_info", "Spitalizare", "Fișa medicală 003/e", "Encounter"),
    "discharge_summary": ("other_med_info", "Extras din fișa medicală a bolnavului de staționar", "Formular 027/e", "DocumentReference"),
    "referral": ("other_med_info", "Trimitere-extras", "Formular 027/e", "DocumentReference"),
    "immunization_record": ("other_med_info", "Vaccinare", "Registrul 063/e", "Immunization"),
    "allergy_record": ("other_med_info", "Fișă alergologică", "Fișa medicală 025/e", "DocumentReference"),
    "pregnancy_record": ("other_med_info", "Carnet perinatal", "Carnet perinatal", "DocumentReference"),
}

# Imaging / functional reports: subtype -> [(title, conclusion)]
IMAGING_REPORTS: dict[str, tuple[tuple[str, str], ...]] = {
    "ecg_report": (
        ("Electrocardiogramă de repaus", "Ritm sinusal, FCC 72/min. Axa electrică normală. Fără modificări ischemice acute."),
        ("Electrocardiogramă de repaus", "Fibrilație atrială cu AV 96/min. Modificări nespecifice de repolarizare."),
    ),
    "ultrasound_report": (
        ("Ecografia organelor cavității abdominale", "Ficat cu ecostructură omogenă, dimensiuni normale. Colecist fără calculi. Rinichi fără particularități."),
        ("Ecocardiografie transtoracică", "FE VS 55%. Cavități cardiace nedilatate. Insuficiență mitrală gr. I."),
        ("Ecografia glandei tiroide", "Glanda tiroidă de dimensiuni normale, ecostructură neomogenă difuză."),
    ),
    "xray_report": (
        ("Radiografia cutiei toracice (incidență postero-anterioară)", "Câmpuri pulmonare fără opacități de focar. Sinusuri costo-diafragmatice libere. Cord în limite normale."),
        ("Radiografia articulației genunchiului drept", "Îngustarea spațiului articular, osteofite marginale — gonartroză gr. II."),
    ),
    "ct_report": (
        ("Tomografie computerizată cerebrală nativă", "Fără semne de hemoragie intracraniană. Zonă hipodensă în teritoriul ACM stângi, compatibilă cu ischemie recentă."),
    ),
    "mri_report": (
        ("RMN coloana vertebrală lombară", "Protruzie discală L4–L5 fără compresiune radiculară semnificativă."),
    ),
    "endoscopy_report": (
        ("Fibroesofagogastroduodenoscopie", "Mucoasa gastrică hiperemiată în regiunea antrală. Test rapid H. pylori negativ."),
    ),
    "microbiology_report": (
        ("Urocultură cu antibiogramă", "Escherichia coli 10^5 UFC/ml, sensibil la ceftriaxonă și nitrofurantoină."),
    ),
}

FIRST_SPECIALIST_EXAMS = (
    "medic de familie", "oftalmolog", "otorinolaringolog", "neurolog", "psihiatru", "narcolog",
)

MOLDOVAN_SURNAMES = (
    "Rusu", "Ceban", "Popa", "Moraru", "Cojocaru", "Lungu", "Țurcanu", "Munteanu",
    "Botnaru", "Bivol", "Croitoru", "Sârbu", "Guțu", "Grosu", "Melnic", "Rotaru",
    "Ursu", "Cebotari", "Railean", "Bodrug", "Plămădeală", "Țîbuleac", "Gheorghiță",
    "Ciobanu", "Vrabie", "Ababii", "Lupu", "Răileanu", "Bejenaru", "Mîrza",
)
