rule lab_decoy_pdf_ttp
{
    meta:
        description = "Identifies PDFs built by the Echo phishing-sim 'decoy PDF kit' -- a reused OpenAction/JavaScript payload embedded regardless of lure content. Demonstrates hunting on a shared TTP across tailored lures (contract, invoice, shipping notice) sent to different targets, rather than matching a single file or a single lure's brand/content. Lab/demo artifact only -- NOT a general phishing or malware detection rule; a match identifies this lab kit's signature, not evidence of an actual malicious payload."
        source       = "Echo phishing-sim lab"

    strings:
        // The reused payload/TTP: identical across every lure family and
        // target, since it's injected by the same kit regardless of
        // whether the document pretends to be a contract, invoice, or
        // customs notice. This is what the rule hunts on.
        $kit1 = "DECOY_NOT_REAL_0011223344556677889900" ascii
        $kit2 = "decoy only: no real payload, for detection-lab/demo use" ascii
        $kit3 = "app.alert('Simulated phishing lure. No real payload. Lab/demo use only.');" ascii
        $kit4 = "ROP_CHAIN" ascii

    condition:
        2 of ($kit*)
}
