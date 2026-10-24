# Evidence archives

Historical archive (unchanged): `/workspace/scratch/deck-master-unified-20261024-evidence.tar.gz`

SHA256: `aec438be2e67e73967b639a8d56d803590c0b377422e5ebb95267a0c2a95cab6`. Its 120-file manifest is preserved in historical-evidence-manifest.json. It contains original failures/retries and the earlier75551e7d/1c9d9231 evidence; these are not the final candidate.

New stability archive: `/workspace/scratch/deck-master-unified-stability-20261024-evidence.tar.gz`

SHA256: `af553ba5f9185ac0cfe6e8830079423a000df1390e9ed9667433bda800629fd3`; 708 files; 32711315 bytes. evidence-manifest.json lists each included file hash. The authoritative final report snapshot is under review-materials/ (the self-hashing archive index is excluded). The full code patch contains the reports as they existed at its code SHA; use the final review-materials snapshot for this handoff. It includes frozen full source/wheel results, installation proof, actual render artifacts, browser/production-flow evidence, all first failures and interrupted attempts, reproduction scripts, wheels, Q2 logs and all61 observations for each final run. Generated large Q2 installation/project trees are excluded; their execution/identity records are retained.

Packaged runtime is b66cec184e20bbfb34a133980e9ca92bbeb7e9bf; final test/CI identity is in sources.json. These local archives can be attached to the user-selected Pro review. They are not claimed to be hosted at a PR URL. No Pro review or final merge has run.
