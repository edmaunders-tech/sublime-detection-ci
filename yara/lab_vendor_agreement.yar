import "hash"

rule lab_Vendor_Services_Agreement_AGH_2026_00417
{
    meta:
        description = "Exact match for simulated vendor agreement lab sample (Echo phishing-sim demo). Identifies this specific lab artifact only -- NOT a general phishing/malware detection rule, and a match is not evidence of a malicious payload."
        source       = "Echo phishing-sim lab"
        sha256       = "2ec830eadd44c693957a0c82ecc0e3206322c79c545774cb1ad848ccc953797a"

    condition:
        hash.sha256(0, filesize) == "2ec830eadd44c693957a0c82ecc0e3206322c79c545774cb1ad848ccc953797a"
}
