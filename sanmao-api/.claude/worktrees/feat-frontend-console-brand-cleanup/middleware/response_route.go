package middleware

import (
	"errors"
	"net/http"
	"strings"

	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/types"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func ResolveResponseRoute() func(c *gin.Context) {
	return func(c *gin.Context) {
		responseID := strings.TrimSpace(c.Param("response_id"))
		if responseID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": types.OpenAIError{
					Message: "response_id is required",
					Type:    "invalid_request_error",
					Code:    "invalid_request_error",
				},
			})
			c.Abort()
			return
		}

		userID := c.GetInt("id")
		routeInfo, err := model.FindResponseRouteInfoByResponseID(userID, responseID)
		if err != nil {
			status := http.StatusNotFound
			if !errors.Is(err, gorm.ErrRecordNotFound) {
				status = http.StatusInternalServerError
			}
			c.JSON(status, gin.H{
				"error": types.OpenAIError{
					Message: "response route not found",
					Type:    "invalid_request_error",
					Code:    "response_not_found",
				},
			})
			c.Abort()
			return
		}

		c.Set("specific_channel_id", routeInfo.ChannelIdString())
		c.Set("forced_model_name", routeInfo.ModelName)
		c.Next()
	}
}
