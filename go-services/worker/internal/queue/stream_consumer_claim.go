package queue

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/logger"
)

// ackMessage acknowledges a message in the stream
func (c *Consumer) ackMessage(ctx context.Context, messageID string) {
	log := logger.GetLogger()

	err := c.redis.XAck(ctx, c.streamName, c.consumerGroup, messageID).Err()
	if err != nil {
		log.Errorf("failed to ACK message, message_id=%s, error=%v", messageID, err)
	}
}

// claimStalledMessages periodically checks for and claims stalled messages
func (c *Consumer) claimStalledMessages(ctx context.Context) {
	log := logger.GetLogger()
	ticker := time.NewTicker(ClaimCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Infof("stalled message claimer stopped, worker_id=%s", c.workerID)
			return
		case <-ticker.C:
			c.checkAndClaimPending(ctx)
		}
	}
}

// checkAndClaimPending checks for pending messages and claims stalled ones
func (c *Consumer) checkAndClaimPending(ctx context.Context) {
	log := logger.GetLogger()

	// Get pending messages summary
	pending, err := c.redis.XPending(ctx, c.streamName, c.consumerGroup).Result()
	if err != nil {
		log.Errorf("failed to get pending summary: %v", err)
		return
	}

	if pending.Count == 0 {
		return
	}

	log.Debugf("checking pending messages, count=%d, stream=%s", pending.Count, c.streamName)

	// Get detailed pending messages
	pendingExt, err := c.redis.XPendingExt(ctx, &redis.XPendingExtArgs{
		Stream: c.streamName,
		Group:  c.consumerGroup,
		Start:  "-",
		End:    "+",
		Count:  MaxPendingToCheck,
	}).Result()
	if err != nil {
		log.Errorf("failed to get pending messages detail: %v", err)
		return
	}

	// Claim stalled messages
	for _, pendingMsg := range pendingExt {
		// Skip messages that haven't been idle long enough
		if pendingMsg.Idle < ClaimIdleThreshold {
			continue
		}

		// Skip messages owned by this consumer (we're already processing them)
		if pendingMsg.Consumer == c.consumerName {
			continue
		}

		log.Infof("claiming stalled message, message_id=%s, idle=%v, owner=%s",
			pendingMsg.ID, pendingMsg.Idle, pendingMsg.Consumer)

		// Claim the message
		messages, err := c.redis.XClaim(ctx, &redis.XClaimArgs{
			Stream:   c.streamName,
			Group:    c.consumerGroup,
			Consumer: c.consumerName,
			MinIdle:  ClaimIdleThreshold,
			Messages: []string{pendingMsg.ID},
		}).Result()
		if err != nil {
			log.Errorf("failed to claim message %s: %v", pendingMsg.ID, err)
			continue
		}

		// Process claimed messages
		for _, msg := range messages {
			log.Infof("processing claimed message, message_id=%s", msg.ID)
			c.processMessage(ctx, msg)
		}
	}
}
