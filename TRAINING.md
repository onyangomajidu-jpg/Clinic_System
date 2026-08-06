# User Training Guide — Clinic Management System v1.0-beta

This guide is designed to train clinic staff in under one working day (NFR-3).
It covers the daily workflows for each role.

---

## 1. Quick Overview

The Clinic Management System helps you:
- Register patients and keep their records
- Record visits, diagnoses, and prescriptions
- Dispense drugs and track pharmacy stock
- Generate invoices and record payments
- Schedule appointments and send SMS reminders
- View reports for clinic management

**Key principle:** The system works **offline** — you don't need internet
to use it. Data syncs automatically when connectivity is available.

---

## 2. Logging In

1. Open your browser (Chrome, Firefox, or Edge)
2. Go to the clinic system address (e.g., `http://localhost:8000`)
3. Enter your **username** and **password**
4. Click **Log in**

> **Tip:** If you forget your password, ask the clinic administrator to reset it.

---

## 3. Receptionist / Records Clerk

### 3.1 Register a New Patient (UR-1)

1. From the dashboard, click **Register Patient**
2. Fill in:
   - **Full name** (required)
   - **Sex** (required)
   - **Date of birth** OR **Estimated age** (one is required)
   - Phone number (if available)
   - Village, parish, district
   - Next of kin (optional)
3. Click **Save**
4. The system assigns a **patient card number** (e.g., CL-2026-0001)
5. Click **Print Card** to give the patient their card

### 3.2 Search for a Patient (UR-2)

1. Click **Search Patients**
2. Type any of:
   - Part of the name (e.g., "nak" finds "Nakato Aisha")
   - Phone number (with or without spaces)
   - Card number (e.g., CL-2026-0001)
3. Click **Search**
4. Click on the patient to view their record

### 3.3 Check Outstanding Balance (UR-4)

Before referring a patient to the doctor, check if they have an unpaid
balance. The **Billing Dashboard** shows all patients with outstanding
balances.

### 3.4 Schedule an Appointment (UR-24)

1. From the patient's record, click **Schedule Appointment**
2. Choose the **date and time**
3. Enter the **reason** for the appointment
4. Click **Save**

The system will send an **SMS reminder** to the patient's phone before the
appointment date.

---

## 4. Nurse / Clinical Officer / Doctor

### 4.1 Record a Visit (UR-7)

1. Search for the patient
2. Click **Record Visit**
3. Fill in:
   - **Visit type** (outpatient, follow-up, emergency, antenatal)
   - **Chief complaint** (what the patient says is wrong)
   - **Diagnosis** (select from the quick-pick list or type)
   - **Vitals**: blood pressure, pulse, temperature, weight
   - **Notes** (optional)
4. Click **Save**

### 4.2 Prescribe Drugs (UR-8)

1. From the visit detail page, click **Add Prescription**
2. Select the **drug** (only drugs in stock are shown)
3. Enter:
   - **Dosage** (e.g., 500mg)
   - **Frequency** (e.g., 3 times a day)
   - **Duration** (e.g., 7 days)
   - **Quantity** (e.g., 21 tablets)
4. Click **Save**

> **Note:** You can only prescribe drugs that are in stock. If a drug is
> out of stock, it won't appear in the list.

### 4.3 View Visit History (UR-6)

From the patient's record, click **Visit History** to see all past visits,
diagnoses, and prescriptions.

---

## 5. Pharmacist / Dispenser

### 5.1 View Prescriptions Waiting (UR-11)

The **Pharmacy Dashboard** shows all prescriptions waiting to be dispensed
for the day.

### 5.2 Dispense a Drug (UR-12)

1. From the pharmacy dashboard, click **Dispense** on a prescription
2. Enter the **quantity to dispense**
3. Click **Dispense**
4. The system **automatically reduces stock**

### 5.3 Partial Dispensing (UR-14)

If you only have part of the prescribed quantity:
1. Enter the quantity you **do have** (e.g., 10 instead of 21)
2. Click **Dispense**
3. The remaining quantity stays on the prescription for later

### 5.4 Low Stock & Expiry Alerts (UR-13)

The pharmacy dashboard shows:
- **Low stock alerts** — drugs below their reorder level
- **Near-expiry alerts** — drugs expiring within 90 days

Reorder these drugs in time!

### 5.5 Restock Drugs

1. From the drug list, click **Restock** on a drug
2. Enter the quantity received
3. Add notes (e.g., "Monthly delivery from NMS")
4. Click **Save**

The system records who restocked and when (audit trail).

---

## 6. Billing Staff / Cashier

### 6.1 Generate an Invoice (UR-15)

1. From the visit, click **Generate Invoice**
2. The system automatically includes:
   - Consultation fee
   - Dispensed drugs
   - Lab tests (if applicable)
3. The invoice is created and shown

### 6.2 Record a Payment (UR-16)

1. On the invoice page, enter the **amount paid**
2. Select the **payment method**:
   - **Cash**
   - **Mobile Money** (MTN / Airtel)
   - Insurance
3. Enter the **reference** (e.g., receipt number or MTN transaction ID)
4. Click **Record Payment**

The invoice status updates automatically:
- **Paid** — full amount received
- **Partial** — some amount received (outstanding balance tracked)
- **Unpaid** — no payment yet

### 6.3 Print a Receipt (UR-17)

After payment, click **Print Receipt** to give the patient their receipt.

### 6.4 Daily Collections Summary (UR-18)

At the end of the day, click **Daily Summary** to see:
- Total collected (cash vs mobile money)
- Number of payments
- Outstanding balances

---

## 7. Clinic Administrator / In-charge

### 7.1 View Reports (UR-19)

From the dashboard, click **Reports** to view:
- **Patient volumes** — daily/weekly patient counts
- **Common diagnoses** — most frequent diagnoses
- **Revenue report** — billed, collected, outstanding
- **Drug usage** — quantities dispensed per drug

Reports can be **exported as CSV** for district health reporting (UR-23).

### 7.2 Manage Staff Accounts (UR-20)

Only admins can:
- Create staff accounts
- Assign roles (receptionist, nurse, doctor, pharmacist, admin)
- Reset passwords

### 7.3 Sync Status

The **Sync Status** page shows whether data has been synced to the central
server (multi-clinic deployments). Click **Sync Now** when internet is
available.

---

## 8. Key Tips for Daily Use

### Speed
- Use the **quick-pick diagnosis list** instead of typing
- Search patients by **partial name** or **phone number**
- The patient card number speeds up future visits

### Offline
- The system works **without internet**
- Data is stored locally and synced later
- The **Sync Status** page shows what's waiting to sync

### Data Safety
- Patient data is **private** — only view records for patients you are
  treating (NFR-5)
- Log out when leaving the computer
- Daily automated backups protect against data loss

### Common Errors
| Problem | Solution |
|---|---|
| Can't find a patient | Try searching by phone number or card number |
| Drug not in list | Drug is out of stock — check pharmacy |
| Can't dispense more than remaining | Enter a quantity ≤ remaining |
| Can't pay more than balance | Enter amount ≤ outstanding balance |

---

## 9. Hands-On Practice Exercises

### Exercise 1: Registration (Receptionist)
1. Register a test patient: "Namukasa Sarah", Female, age 28
2. Note the card number assigned
3. Search for the patient by partial name "nam"

### Exercise 2: Visit & Prescription (Nurse)
1. Open the patient from Exercise 1
2. Record a visit: Outpatient, "Fever and headache", diagnosis "Malaria"
3. Add a prescription: Amoxicillin 500mg, 3x/day, 7 days, 21 tablets

### Exercise 3: Dispensing (Pharmacist)
1. Dispense the prescription from Exercise 2
2. Verify stock decreased
3. Check the pharmacy dashboard for alerts

### Exercise 4: Billing (Cashier)
1. Generate an invoice for the visit
2. Record a partial payment (e.g., 2000 UGX cash)
3. Record the remaining balance via Mobile Money
4. Print the receipt

### Exercise 5: Reports (Admin)
1. View the patient volumes report
2. View the revenue report
3. Export the drug usage report as CSV

---

## 10. Checklist for First Day

- [ ] Can log in and log out
- [ ] Can register a patient
- [ ] Can search for a patient
- [ ] Can record a visit with vitals
- [ ] Can prescribe a drug
- [ ] Can dispense a drug
- [ ] Can generate an invoice
- [ ] Can record a payment
- [ ] Can print a receipt
- [ ] Can schedule an appointment
- [ ] Can view reports
- [ ] Can see sync status