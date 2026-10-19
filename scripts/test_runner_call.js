const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

async function test() {
    const tmpInput = path.join(os.tmpdir(), 'zk_input_test.json');
    const inputData = {
        payloadHex: 'a1b2c3d4',
        imageSha256: '3036c3933c3413a7b63f533a1e4c029471131ef5e1428359be24419ad2231bfa',
        modelDigest: 'ea248d68436673aad958563c5b4cec25bb3669ecd3aeda28a1775fa137c610aa',
        nonceHex: '123456',
        secretKeyHex: 'abcdef'
    };
    fs.writeFileSync(tmpInput, JSON.stringify(inputData));

    console.log("Calling prover_runner.js prove...");
    const runnerScript = path.resolve('backend/zk/prover_runner.js');
    const cmdProve = `node "${runnerScript}" prove "${tmpInput}"`;
    const proveOut = execSync(cmdProve, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });
    const proveRes = JSON.parse(proveOut);
    console.log("[+] Proof Generated:", proveRes.is_valid, "in", proveRes.proving_time_seconds, "s");

    console.log("Calling prover_runner.js verify...");
    const tmpVerify = path.join(os.tmpdir(), 'zk_verify_test.json');
    fs.writeFileSync(tmpVerify, JSON.stringify({
        proof: proveRes.proof,
        publicSignals: proveRes.publicSignals
    }));
    const cmdVerify = `node "${runnerScript}" verify "${tmpVerify}"`;
    const verifyOut = execSync(cmdVerify, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });
    const verifyRes = JSON.parse(verifyOut);
    console.log("[+] Verification Result:", verifyRes);
}

test().catch(err => {
    console.error("Runner test failed:", err);
    process.exit(1);
});
