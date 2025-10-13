package interfaces

import (
	"github.com/hyperledger/fabric-protos-go/common"
)

// HistoryEntry represents a single history entry from Fabric
type HistoryEntry struct {
	TxID      string             `json:"txId"`
	Timestamp *common.Timestamp  `json:"timestamp"`
	IsDelete  bool               `json:"isDelete"`
	Value     []byte             `json:"value"`
}