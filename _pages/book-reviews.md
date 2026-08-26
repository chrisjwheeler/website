---
layout: default
title: Book reviews
permalink: /book-reviews/
category: book-reviews
---

<section class="category-page">

    <p class="eyebrow">01 · Book reviews</p>

    <h1>Book reviews</h1>

    <div class="post-list">

        {% assign posts = site.posts
            | where: "category", "book-reviews" %}

        {% for post in posts %}

        <a href="{{ post.url | relative_url }}"
           class="post-row">

            <span class="post-date">
                {{ post.date | date: "%d.%m.%y" }}
            </span>

            <div>

                <h2>
                    {{ post.title }}
                </h2>

                {% if post.excerpt %}
                <p>
                    {{ post.excerpt | strip_html | truncate: 140 }}
                </p>
                {% endif %}

            </div>

            <span class="arrow">↗</span>

        </a>

        {% endfor %}

    </div>

</section>
