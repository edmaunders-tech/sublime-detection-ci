rule lab_vendor_agreement_kit
{
    meta:
        description = "Identifies PDFs built from the Echo phishing-sim 'vendor agreement' lab kit: same decoy payload/template reused with personalized recipient, contract ref, and amount. Demonstrates detecting a reused kit across targets, not a single exact file. Lab/demo artifact only -- NOT a general phishing or malware detection rule; a match is not evidence of a malicious payload."
        source       = "Echo phishing-sim lab"

    strings:
        // Group A: the reused decoy "payload" infrastructure (identical
        // across every variant, regardless of personalization) -- stands
        // in for an attacker's reused phishing-kit backend/script.
        $kit1 = "DECOY_NOT_REAL_0011223344556677889900" ascii
        $kit2 = "decoy only: no real payload, for detection-lab/demo use" ascii
        $kit3 = "app.alert('Simulated phishing lure. No real payload. Lab/demo use only.');" ascii
        $kit4 = "ROP_CHAIN" ascii

        // Group B: the reused lure template/brand -- stands in for an
        // attacker reusing the same impersonated company across targets,
        // with only the contract reference personalized per recipient.
        $brand = "ACME GLOBAL HOLDINGS LTD" ascii wide
        $ref   = /AGH-2026-[0-9]{5}/ ascii

    condition:
        2 of ($kit*)
        and any of ($brand, $ref)
}
