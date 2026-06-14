// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title NexusVectorProofRegistry
/// @notice Stores verifiable AI risk decision hashes for Nexus Vector.
/// @dev Hackathon MVP contract designed for Mantle-compatible EVM deployment.
contract NexusVectorProofRegistry {
    struct DecisionProof {
        bytes32 proofId;
        bytes32 decisionHash;
        string decisionId;
        string agent;
        string metadataURI;
        address submitter;
        uint256 chainId;
        uint256 createdAt;
        bool exists;
    }

    mapping(bytes32 => DecisionProof) private proofs;
    bytes32[] private proofIds;

    event DecisionProofRegistered(
        bytes32 indexed proofId,
        bytes32 indexed decisionHash,
        string decisionId,
        string agent,
        string metadataURI,
        address indexed submitter,
        uint256 chainId,
        uint256 createdAt
    );

    function registerDecisionProof(
        string calldata decisionId,
        bytes32 decisionHash,
        string calldata agent,
        string calldata metadataURI
    ) external returns (bytes32 proofId) {
        require(bytes(decisionId).length > 0, "decisionId required");
        require(decisionHash != bytes32(0), "decisionHash required");
        require(bytes(agent).length > 0, "agent required");

        proofId = keccak256(
            abi.encodePacked(
                block.chainid,
                msg.sender,
                agent,
                decisionId,
                decisionHash
            )
        );

        require(!proofs[proofId].exists, "proof already exists");

        proofs[proofId] = DecisionProof({
            proofId: proofId,
            decisionHash: decisionHash,
            decisionId: decisionId,
            agent: agent,
            metadataURI: metadataURI,
            submitter: msg.sender,
            chainId: block.chainid,
            createdAt: block.timestamp,
            exists: true
        });

        proofIds.push(proofId);

        emit DecisionProofRegistered(
            proofId,
            decisionHash,
            decisionId,
            agent,
            metadataURI,
            msg.sender,
            block.chainid,
            block.timestamp
        );
    }

    function getProof(bytes32 proofId)
        external
        view
        returns (DecisionProof memory)
    {
        require(proofs[proofId].exists, "proof not found");
        return proofs[proofId];
    }

    function verifyDecisionHash(bytes32 proofId, bytes32 decisionHash)
        external
        view
        returns (bool)
    {
        return proofs[proofId].exists && proofs[proofId].decisionHash == decisionHash;
    }

    function getProofCount() external view returns (uint256) {
        return proofIds.length;
    }

    function getProofIdAt(uint256 index) external view returns (bytes32) {
        require(index < proofIds.length, "index out of range");
        return proofIds[index];
    }
}
