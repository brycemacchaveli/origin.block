module github.com/blockchain-financial-platform/fabric-chaincode/loan

go 1.21

require (
	github.com/blockchain-financial-platform/fabric-chaincode/shared v0.0.0
	github.com/hyperledger/fabric-chaincode-go v0.0.0-20220920210243-7bc6fa0dd58b
	github.com/hyperledger/fabric-protos-go v0.0.0-20220827195505-ce4c067a561d
	github.com/stretchr/testify v1.8.4
)

replace github.com/blockchain-financial-platform/fabric-chaincode/shared => ../shared