# Chapter 2 -- Business Requirements & Scope

**Document Version:** 1.0\
**Project:** Price Drop Notification System\
**Document Type:** Software Architecture Document (SAD)\
**Chapter:** 02 -- Business Requirements & Scope

------------------------------------------------------------------------

# 1. Purpose

This chapter defines the business objectives, scope, stakeholders,
assumptions, constraints, and success criteria for the Price Drop
Notification System.

It establishes **what the system is expected to achieve from a business
perspective**, independent of implementation details. These business
requirements serve as the foundation for all subsequent architecture and
design decisions.

------------------------------------------------------------------------

# 2. Business Problem Statement

Online shoppers frequently purchase products from e-commerce platforms
such as Amazon. Product prices fluctuate due to sales, promotional
campaigns, inventory adjustments, and dynamic pricing strategies.

Customers who are interested in purchasing a product often face several
challenges:

-   They must manually revisit product pages to check prices.
-   They may miss temporary discounts.
-   Tracking multiple products across different days is inconvenient.
-   There is no simple mechanism to notify users when prices decrease.

As a result, customers either spend unnecessary time monitoring products
or miss opportunities to purchase at lower prices.

The objective of this project is to automate price tracking and
proactively notify users whenever the product price decreases.

------------------------------------------------------------------------

# 3. Business Objectives

-   Provide an easy way for users to monitor product prices.
-   Automatically detect price changes.
-   Notify users immediately when prices drop.
-   Maintain historical pricing information.
-   Minimize infrastructure and operational costs.
-   Build a scalable architecture that supports future enhancements.
