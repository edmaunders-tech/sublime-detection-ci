rule auto_Vendor_Services_Agreement_AGH_2026_00417
{
    meta:
        description = "Auto-generated from flagged sample Vendor_Services_Agreement_AGH-2026-00417.pdf"
        source       = "Falcon Fusion SOAR auto-yara step"
        sha256       = "2ec830eadd44c693957a0c82ecc0e3206322c79c545774cb1ad848ccc953797a"

    strings:
        $s0 = "BT /F1 11 Tf 16 TL 72 740 Td (ACME GLOBAL HOLDINGS LTD) Tj T* ( ) Tj T* (VENDOR SERVICES AGREEMENT) Tj T* (Contract Reference: AGH-2026-00417) Tj T* ( ) Tj T* (This Agreement is made effective as of the date of last signature) Tj T* (below, by and between Acme Global Holdings Ltd \("Client"\) and the) Tj T* (undersigned service provider \("Vendor"\), for the provision of) Tj T* (professional consulting services as described in Schedule A.) Tj T* ( ) Tj T* (1. TERM) Tj T* (   This Agreement shall commence on the Effective Date and continue) Tj T* (   for a period of twelve \(12\) months unless terminated earlier.) Tj T* ( ) Tj T* (2. FEES) Tj T* (   Client shall pay Vendor the fees set out in Schedule A within) Tj T* (   thirty \(30\) days of receipt of a valid invoice.) Tj T* ( ) Tj T* (3. CONFIDENTIALITY) Tj T* (   Each party shall keep confidential all non-public information) Tj T* (   disclosed by the other party in connection with this Agreement.) Tj T* ( ) Tj T* (    *** SIMULATED DOCUMENT -- PHISHING-SIM / LAB DEMO ONLY ***) Tj T* (    *** NOT A REAL CONTRACT -- NO REAL PAYLOAD IN THIS FILE ***) Tj ET" ascii wide
        $s1 = "BT /F1 11 Tf 16 TL 72 740 Td (SIGNATURE PAGE) Tj T* ( ) Tj T* (IN WITNESS WHEREOF, the parties have executed this Agreement as) Tj T* (of the date\(s\) set forth below.) Tj T* ( ) Tj T* (ACME GLOBAL HOLDINGS LTD) Tj T* ( ) Tj T* (Signature: ____________________________) Tj T* (Name:      J. Whitfield) Tj T* (Title:     Director of Procurement) Tj T* (Date:      ____________________________) Tj T* ( ) Tj T* ( ) Tj T* (VENDOR) Tj T* ( ) Tj T* (Signature: ____________________________) Tj T* (Name:      ____________________________) Tj T* (Title:     ____________________________) Tj T* (Date:      ____________________________) Tj T* ( ) Tj T* ( ) Tj T* (    *** SIMULATED DOCUMENT -- PHISHING-SIM / LAB DEMO ONLY ***) Tj ET" ascii wide
        $s2 = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 6 0 R /F2 7 0 R >> >> /Contents 5 0 R >>" ascii wide
        $s3 = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 6 0 R /F2 7 0 R >> >> /Contents 9 0 R >>" ascii wide
        $s4 = "app.alert('Simulated phishing lure. No real payload. Lab/demo use only.');" ascii wide
        $s5 = "// --- decoy only: no real payload, for detection-lab/demo use ---" ascii wide
        $s6 = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>" ascii wide
        $s7 = "var ROP_CHAIN = '41414141414141414141414141414141414141';" ascii wide

    condition:
        hash.sha256(0, filesize) == "2ec830eadd44c693957a0c82ecc0e3206322c79c545774cb1ad848ccc953797a"
        or 3 of them
}
