module github.com/blockchain-financial-platform/fabric-chaincode/compliance

go 1.21

require (
	github.com/blockchain-financial-platform/fabric-chaincode/shared v0.0.0
	github.com/hyperledger/fabric-chaincode-go v0.0.0-20220920210243-7bc6fa0dd58b
	github.com/hyperledger/fabric-protos-go v0.0.0-20220827195505-ce4c067a561d
	github.com/stretchr/testify v1.8.4
)

replace github.com/blockchain-financial-platform/fabric-chaincode/shared => ../shared

require (
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/golang/protobuf v1.5.2 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	golang.org/x/net v0.0.0-20220708220712-1185a9018129 // indirect
	golang.org/x/sys v0.26.0 // indirect
	golang.org/x/text v0.3.7 // indirect
	google.golang.org/genproto v0.0.0-20220718134204-073382fd740c // indirect
	google.golang.org/grpc v1.48.0 // indirect
	google.golang.org/protobuf v1.28.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)
